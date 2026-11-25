import ast, copy, json, unittest, os, tempfile, io, urllib.request, urllib.error
from unittest.mock import patch
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from krea2_i2i import configure_i2i, comfy_input_directory

# Execute the actual production LoRA wiring without importing the GPU/service runtime.
_tree = ast.parse((ROOT / "handler.py").read_text())
_funcs = [n for n in _tree.body if isinstance(n, ast.FunctionDef) and n.name in ("apply_dynamic_loras_to_model_chain", "apply_dynamic_loras_to_krea2_workflow")]
_scope = {}
exec(compile(ast.Module(body=_funcs, type_ignores=[]), "handler.py", "exec"), _scope)

class KreaI2ITest(unittest.TestCase):
    def build(self, **overrides):
        args = dict(image_path="/dev/shm/source.bin", prompt="a red cube", seed=42, steps=8, cfg=1, width=768, height=512, denoise=0.35)
        args.update(overrides)
        return configure_i2i(json.loads((ROOT / "workflow/krea2_i2i.json").read_text()), **args)

    def test_source_replaces_empty_latent_and_uses_krea_weights(self):
        g=self.build()
        self.assertNotIn("13", g)
        self.assertEqual(g["3"]["inputs"]["latent_image"], ["62", 0])
        self.assertEqual(g["62"]["inputs"], {"pixels":["63",0],"vae":["29",0]})
        self.assertEqual(g["63"]["inputs"]["image"], ["61",0])
        self.assertEqual(g["63"]["inputs"]["width"],768)
        self.assertEqual(g["63"]["inputs"]["height"],512)
        self.assertEqual(g["28"]["inputs"]["unet_name"],"krea2_turbo_fp8_scaled.safetensors")
        self.assertEqual(g["30"]["inputs"]["type"],"krea2")
        self.assertEqual(g["29"]["inputs"]["vae_name"],"qwen_image_vae.safetensors")

    def test_zero_and_full_denoise_preserved(self):
        for d in (0,0.35,1):
            g=self.build(denoise=d)
            self.assertEqual(g["3"]["inputs"]["denoise"],d)
            self.assertEqual(g["3"]["inputs"]["seed"],42)
            self.assertEqual(g["3"]["inputs"]["steps"],8)

    def test_invalid_denoise_fails(self):
        for d in (-1,1.1,float("nan"),float("inf")):
            with self.assertRaises(ValueError):self.build(denoise=d)

    def test_missing_source_fails(self):
        with self.assertRaises(ValueError):self.build(image_path="")

    def test_eight_loras_chain_to_krea_sampler_and_keep_latent(self):
        g=self.build()
        loras=[[f"lora{i}.safetensors", w] for i,w in enumerate([0,-0.5,1,0.8,0.2,0.3,0.4,0.5])]
        _scope["apply_dynamic_loras_to_krea2_workflow"](g,loras)
        self.assertEqual(g["3"]["inputs"]["model"],["6507",0])
        self.assertEqual(g["6500"]["inputs"]["model"],["28",0])
        self.assertEqual(g["6500"]["inputs"]["strength_model"],0)
        self.assertEqual(g["6501"]["inputs"]["strength_model"],-0.5)
        self.assertEqual(g["3"]["inputs"]["latent_image"],["62",0])

    def test_negative_uses_correct_encoder(self):
        g=self.build(negative_prompt="blurry",cfg=2)
        self.assertEqual(g["34"]["inputs"],{"text":"blurry","clip":["30",0]})
        self.assertEqual(g["3"]["inputs"]["negative"],["34",0])

    def test_decrypted_source_stays_inside_comfy_input_root(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {"RUNTIME_ROOT": root}):
            target = Path(comfy_input_directory("task_test")) / "condition_image.png"
            target.write_bytes(b"source")
            base = Path(root) / "input"
            self.assertEqual(os.path.commonpath([base, target]), str(base))
            self.assertTrue(target.is_file())
            g = self.build(image_path=str(target))
            self.assertEqual(g["61"]["inputs"]["image"], str(target))

    def test_task_path_rejects_escape(self):
        for value in ("../escape", "/tmp/escape", "", ".", ".."):
            with self.assertRaises(ValueError): comfy_input_directory(value)

    def test_graph_error_reports_codes_without_prompt_or_paths(self):
        scope = {"urllib": urllib, "json": json, "server_address": "127.0.0.1", "client_id": "test", "logger": type("Log", (), {"info": lambda self,*args: None})()}
        fn = next(n for n in _tree.body if isinstance(n, ast.FunctionDef) and n.name == "queue_prompt")
        exec(compile(ast.Module(body=[fn], type_ignores=[]), "handler.py", "exec"), scope)
        body = {"node_errors": {"61": {"errors": [{"type": "custom_validation_failed", "details": "PRIVATE PROMPT /private/source"}]}}}
        failure = urllib.error.HTTPError("http://127.0.0.1/prompt", 400, "Bad Request", {}, io.BytesIO(json.dumps(body).encode()))
        with patch("urllib.request.urlopen", side_effect=failure), self.assertRaises(RuntimeError) as result:
            scope["queue_prompt"]({})
        self.assertIn("61:custom_validation_failed", str(result.exception))
        self.assertNotIn("PRIVATE", str(result.exception))
        self.assertNotIn("/private", str(result.exception))

    def test_text_graph_still_empty_latent_and_full_denoise(self):
        g=json.loads((ROOT/"workflow/krea2.json").read_text())
        self.assertEqual(g["3"]["inputs"]["latent_image"],["13",0])
        self.assertEqual(g["3"]["inputs"]["denoise"],1)

if __name__ == "__main__":unittest.main()
