import ast, copy, hashlib, io, json, sys, tempfile, unittest
from pathlib import Path
from PIL import Image, ImageDraw
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from krea2_regional_workflow import configure_regional,prepare_regions,validate_regions

class RegionalTest(unittest.TestCase):
    def fixture(self):
        im=Image.new("L",(512,512));ImageDraw.Draw(im).polygon([(0,0),(240,20),(220,512),(0,512)],fill=255)
        buf=io.BytesIO();im.save(buf,format="PNG");data=buf.getvalue()
        binding={"job_id":"job","model_id":"krea2-turbo","attempt_id":"attempt","direction":"engui_to_endpoint"}
        region={"prompt":"subject","loras":[["a.safetensors",.8]],"mask_role":"region_mask_0","mask_sha256":hashlib.sha256(data).hexdigest()}
        desc={"role":"region_mask_0","envelope":{"binding":{**binding,"role":"region_mask_0","kind":"image"}}}
        return {"__regional_authenticated":True,"__secure_binding":binding,"regional":{"regions":[region]},"media_inputs":[desc]},data
    def prepare(self,inp,data):
        with tempfile.TemporaryDirectory() as d:
            def decrypt(desc,p):Path(p).write_bytes(data)
            return prepare_regions(inp,d,512,512,decrypt,lambda x:x)
    def test_polygon_png_and_exact_lora_strength_survive(self):
        inp,data=self.fixture();result=self.prepare(inp,data)
        self.assertEqual(result[0]["loras"],[["a.safetensors",.8]])
        self.assertTrue(result[0]["mask_path"].endswith("region_mask_0.png"))
    def test_swapped_job_attempt_role_or_hash_rejected(self):
        for key in ["job_id","model_id","attempt_id","role","direction","kind"]:
            inp,data=self.fixture();inp["media_inputs"][0]["envelope"]["binding"][key]="wrong"
            with self.assertRaises(ValueError):self.prepare(inp,data)
        inp,data=self.fixture();inp["regional"]["regions"][0]["mask_sha256"]="0"*64
        with self.assertRaises(ValueError):self.prepare(inp,data)
    def test_plaintext_and_duplicate_descriptor_rejected(self):
        inp,data=self.fixture();inp["__regional_authenticated"]=False
        with self.assertRaises(ValueError):self.prepare(inp,data)
        inp,data=self.fixture();inp["media_inputs"]*=2
        with self.assertRaises(ValueError):self.prepare(inp,data)
    def test_wrong_size_empty_colored_transparent_masks_rejected(self):
        for im in [Image.new("L",(256,512),255),Image.new("L",(512,512),0),Image.new("RGB",(512,512),"red"),Image.new("RGBA",(512,512),(255,255,255,0))]:
            inp,_=self.fixture();buf=io.BytesIO();im.save(buf,format="PNG");data=buf.getvalue()
            inp["regional"]["regions"][0]["mask_sha256"]=hashlib.sha256(data).hexdigest()
            with self.assertRaises(ValueError):self.prepare(inp,data)
    def test_graph_is_copy_and_isolates_each_adapter(self):
        g=json.loads((ROOT/"workflow/krea2.json").read_text());before=copy.deepcopy(g)
        regions=[{"prompt":"left","loras":[["left.safetensors",.9]],"mask_path":"/tmp/left.png"},{"prompt":"right","loras":[["right.safetensors",1.1]],"mask_path":"/tmp/right.png"}]
        new=configure_regional(g,regions)
        self.assertEqual(g,before)
        self.assertEqual(new["regional_0_lora_0"]["inputs"]["lora_name"],"left.safetensors")
        self.assertEqual(new["regional_1_lora_0"]["inputs"]["lora_name"],"right.safetensors")
        self.assertEqual(new["regional_1"]["inputs"]["prev_regions"],["regional_0",0])
        self.assertEqual(new["3"]["inputs"]["model"],["regional_apply",0])
        self.assertEqual(new["regional_apply"]["inputs"]["unmaskable_layers"],"skip")
        self.assertEqual(new["regional_apply"]["inputs"]["adaptive_masks"],"off")
        self.assertEqual(new["3"]["inputs"]["scheduler"],before["3"]["inputs"]["scheduler"])
        self.assertEqual(new["3"]["inputs"]["steps"],before["3"]["inputs"]["steps"])
        self.assertEqual(new["3"]["inputs"]["latent_image"],before["3"]["inputs"]["latent_image"])
    def test_limits_and_nonfinite_weights(self):
        for weight in [float("nan"),float("inf"),True,11,"1"]:
            inp,_=self.fixture();inp["regional"]["regions"][0]["loras"][0][1]=weight
            with self.assertRaises(ValueError):validate_regions(inp["regional"],512,512)
        inp,_=self.fixture()
        for size in [(2048,2048),(513,512),(256,512)]:
            with self.assertRaises(ValueError):validate_regions(inp["regional"],*size)
    def test_production_decrypt_and_logging_preserve_privacy(self):
        tree=ast.parse((ROOT/"handler.py").read_text())
        names={"decrypt_secure_input","sanitize_for_logging"}
        # Handler's logging helper name can vary; test the actual redaction function.
        redactor=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and "'[REDACTED]'" in ast.unparse(n) and "masked" in ast.unparse(n))
        dec=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="decrypt_secure_input")
        scope={"decrypt_structured_envelope":lambda x:{"regional":{"regions":[{"prompt":"private"}]}}}
        exec(compile(ast.Module(body=[dec,redactor],type_ignores=[]),"handler.py","exec"),scope)
        out=scope["decrypt_secure_input"]({"_secure":{"binding":{"job_id":"j"},"wrapped_key":{"v":1}}})
        self.assertTrue(out["__regional_authenticated"])
        self.assertNotIn("private",str(scope[redactor.name](out)))

if __name__=="__main__":unittest.main()
