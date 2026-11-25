import ast, base64, binascii, copy, hashlib, io, json, logging, os, re, shutil, subprocess, sys, tempfile, time, types, unittest, urllib.request, urllib.error, urllib.parse, uuid
from pathlib import Path
from unittest.mock import patch, Mock
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runtime_inputs import comfy_input_directory
TREE = ast.parse((ROOT / 'handler.py').read_text())
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a8x8AAAAASUVORK5CYII=')

def production_scope():
    scope = dict(globals())
    scope.update(logger=Mock(), server_address='127.0.0.1', client_id='test', WRAPPED_KEY_PREFIX='v1:', websocket=types.SimpleNamespace(WebSocket=Mock))
    exec(compile(ast.Module(body=[n for n in TREE.body if isinstance(n, ast.FunctionDef)], type_ignores=[]), 'handler.py', 'exec'), scope)
    return scope

def envelope(master, binding, plain):
    dek, nonce, wn = os.urandom(32), os.urandom(12), os.urandom(12)
    cipher = AESGCM(dek).encrypt(nonce, plain, json.dumps(binding, sort_keys=True, separators=(',', ':')).encode())
    env = {'v':1, 'binding':binding, 'wrapped_key':'v1:'+base64.b64encode(wn+AESGCM(master).encrypt(wn, dek, b'engui:wrapped-key:v1')).decode(), 'nonce':base64.b64encode(nonce).decode()}
    return env, cipher

class RuntimeInputs(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.master = os.urandom(32)
        self.env = patch.dict(os.environ, {'RUNTIME_ROOT':str(self.root/'runtime'), 'FIELD_ENC_KEY_B64':base64.b64encode(self.master).decode(), 'ZIMAGE_FIELD_ENC_KEY_B64':'', 'ZIMAGE_MOCK_SECURE_FLOW':'0', 'FINISH_CLEANUP_SCRIPT':str(self.root/'absent')})
        self.env.start();self.s = production_scope(); self.seen = []
        self.s['load_workflow'] = lambda name: json.loads((ROOT/name).read_text())
        self.s['collect_db_snapshot'] = lambda: {}
        self.s['collect_cleanup_state'] = lambda: {'history_count':0,'files':{},'db':{}}
        self.s['stage_lora_entries'] = lambda entries: entries
        original_cleanup = self.s['cleanup_runtime_artifacts']
        def cleanup(task_dir):
            exists = os.path.exists
            with patch('os.path.exists', side_effect=lambda p: False if str(p).startswith('/ComfyUI/') else exists(p)):
                original_cleanup(task_dir)
        self.s['cleanup_runtime_artifacts'] = cleanup
        self.s['get_transport_request'] = lambda inp: {'output_dir':str(self.root/'cipher-results'), 'output_file_name':'result.bin'}
    def tearDown(self):
        self.env.stop();self.temp.cleanup()
    def job(self, mode='image_to_image', mime='image/png', loras=None):
        binding={'job_id':'job-test','attempt_id':'attempt-test','model_id':'z-image','direction':'engui_to_endpoint'}
        e,c = envelope(self.master,binding,json.dumps({'prompt':'PRIVATE scene', 'lora':loras or []}).encode());e['ciphertext']=base64.b64encode(c).decode()
        media_env, media_cipher=envelope(self.master,{**binding,'role':'init_image' if mode=='image_to_image' else 'condition_image','kind':'image'},PNG)
        source=self.root/'source-cipher.bin';source.write_bytes(media_cipher)
        return {'id':'provider-test','input':{'task_type':mode,'_secure':e,'media_inputs':[{'role':media_env['binding']['role'],'mime':mime,'storage_path':str(source),'envelope':media_env}],'steps':9,'cfg':1,'seed':42,'width':512,'height':512,'denoise':.3}}
    def execute(self, job, fail=False):
        def output(_ws,graph):
            nodes=[n for n in graph.values() if n['class_type']=='LoadImage']
            for node in nodes:
                p=Path(node['inputs']['image']);self.assertEqual(os.path.commonpath([self.root/'runtime/input',p]),str(self.root/'runtime/input'));self.assertEqual(p.read_bytes(),PNG)
            self.seen.append(copy.deepcopy(graph))
            if fail:raise RuntimeError('simulated graph failure')
            return {'output':[base64.b64encode(PNG).decode()]}, {}, 'comfy-test'
        self.s['get_outputs']=output
        with patch('urllib.request.urlopen', return_value=io.BytesIO(b'{}')):
            return self.s['handler'](job)
    def assert_result(self, result):
        media=result['transport_result']['result_media'];env=media['envelope'];dek=self.s['unwrap_dek'](self.master,env['wrapped_key'])
        self.assertEqual(AESGCM(dek).decrypt(base64.b64decode(env['nonce']),Path(media['storage_path']).read_bytes(),self.s['serialize_binding'](env['binding'])),PNG)
        self.assertEqual(env['binding'],{'job_id':'job-test','model_id':'z-image','attempt_id':'attempt-test','direction':'endpoint_to_engui','role':'result','kind':'image'})
        self.assertEqual(list((self.root/'runtime/input').iterdir()),[])
    def test_secure_i2i_real_crypto_and_cleanup(self):
        self.assert_result(self.execute(self.job()))
        g=self.seen[0];self.assertEqual(g['59:3']['inputs']['denoise'],.3);self.assertEqual(g['59:3']['inputs']['latent_image'],['62',0]);self.assertEqual(g['58']['inputs']['value'],'PRIVATE scene')
    def test_supported_mime_extensions(self):
        for mime,extension in [('image/png','.png'),('image/jpeg','.jpg'),('image/webp','.webp')]:
            with self.subTest(mime=mime):
                self.assert_result(self.execute(self.job(mime=mime)))
                self.assertTrue(self.seen[-1]['61']['inputs']['image'].endswith(extension))
    def test_eight_loras_preserve_zimage_model_chain(self):
        self.assert_result(self.execute(self.job(loras=[[f'local_{i}.safetensors',.25+i/10] for i in range(8)])))
        g=self.seen[0];self.assertNotIn('59:35',g);self.assertEqual(g['59:11']['inputs']['model'],['5507',0]);self.assertEqual(g['5500']['inputs']['model'],['59:28',0]);self.assertEqual(g['5507']['inputs']['strength_model'],.95)
    def test_control_source_uses_same_safe_staging(self):self.assert_result(self.execute(self.job(mode='control')))
    def test_openpose_source_uses_same_safe_staging(self):self.assert_result(self.execute(self.job(mode='openpose_extract')))
    def test_failed_graph_also_removes_decrypted_source(self):
        with self.assertRaisesRegex(RuntimeError,'simulated'):self.execute(self.job(),fail=True)
        self.assertEqual(list((self.root/'runtime/input').iterdir()),[])
    def test_bad_cipher_does_not_reach_graph_and_cleans_dir(self):
        j=self.job();Path(j['input']['media_inputs'][0]['storage_path']).write_bytes(b'bad')
        with self.assertRaisesRegex(Exception,'decrypt'):self.execute(j)
        self.assertEqual(self.seen,[]);self.assertEqual(list((self.root/'runtime/input').iterdir()),[])
    def test_text_only_needs_no_input_image(self):
        j=self.job();j['input']['task_type']='text_to_image';j['input']['media_inputs']=[];self.assert_result(self.execute(j));self.assertFalse(any(n['class_type']=='LoadImage' for n in self.seen[0].values()))
    def test_local_and_base64_sources_are_copied_and_original_kept(self):
        original=self.root/'original.png';original.write_bytes(PNG)
        for kind in ['path','base64']:
            target=comfy_input_directory('task_'+kind);result=self.s['process_input'](str(original) if kind=='path' else base64.b64encode(PNG).decode(),target,'image.png',kind)
            self.assertEqual(Path(result).read_bytes(),PNG);self.assertTrue(original.exists());self.assertEqual(os.path.commonpath([target,result]),target)
    def test_task_directory_private_and_rejects_escape_or_symlink(self):
        p=Path(comfy_input_directory('task_private'));self.assertEqual(p.stat().st_mode&0o777,0o700)
        for name in ['../escape','/tmp/escape','','.','..']:
            with self.assertRaises(ValueError):comfy_input_directory(name)
        (p.parent/'task_link').symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(FileExistsError):comfy_input_directory('task_link')
    def test_http400_reports_node_codes_not_prompt_or_input(self):
        body={'node_errors':{'61':{'errors':[{'type':'custom_validation_failed','details':'PRIVATE scene /private/image.png'}]}}}
        e=urllib.error.HTTPError('http://127.0.0.1/prompt',400,'Bad Request',{},io.BytesIO(json.dumps(body).encode()))
        with patch('urllib.request.urlopen',side_effect=e),self.assertRaisesRegex(RuntimeError,'61:custom_validation_failed') as caught:self.s['queue_prompt']({})
        self.assertNotIn('PRIVATE',str(caught.exception));self.assertNotIn('/private',str(caught.exception))
    def test_non_json_http_error_safe_fallback(self):
        e=urllib.error.HTTPError('http://127.0.0.1/prompt',500,'Bad',{},io.BytesIO(b'secret raw body'))
        with patch('urllib.request.urlopen',side_effect=e),self.assertRaisesRegex(RuntimeError,'HTTP 500.*unavailable') as caught:self.s['queue_prompt']({})
        self.assertNotIn('secret',str(caught.exception))

if __name__ == '__main__':unittest.main()
