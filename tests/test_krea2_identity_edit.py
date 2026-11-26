import ast
import unittest
from pathlib import Path
from unittest.mock import Mock
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from krea2_identity_edit import build_identity_edit, IDENTITY_LORA


class IdentityEditTest(unittest.TestCase):
    def graph(self, **overrides):
        args = dict(image_path="/dev/shm/comfy-runtime/input/task/source.png",
                    prompt="Restage the same character in profile.", seed=42,
                    width=1024, height=1024, steps=8)
        args.update(overrides)
        return build_identity_edit(**args)

    def test_target_is_empty_not_ordinary_i2i(self):
        graph = self.graph()
        self.assertEqual(graph["11"]["inputs"]["latent_image"], ["10", 0])
        self.assertEqual(graph["10"]["class_type"], "EmptySD3LatentImage")
        self.assertEqual(graph["11"]["inputs"]["denoise"], 1)
        self.assertEqual(graph["11"]["inputs"]["cfg"], 1)

    def test_reference_reaches_visual_and_grounded_paths(self):
        g = self.graph()
        self.assertEqual(g["7"]["inputs"]["source_latent"], ["6", 0])
        self.assertEqual(g["7"]["inputs"]["source_image"], ["5", 0])
        self.assertEqual(g["7"]["inputs"]["target_latent"], g["11"]["inputs"]["latent_image"])
        self.assertEqual(g["8"]["inputs"]["image"], ["5", 0])
        self.assertEqual(g["9"]["inputs"]["image"], ["5", 0])
        self.assertEqual(g["9"]["inputs"]["prompt"], "")
        self.assertEqual(g["4"]["inputs"]["lora_name"], IDENTITY_LORA)

    def test_parameters_are_exact_and_chain_preserves_identity(self):
        g = self.graph(seed=73, width=768, height=1024, ref_boost=.6,
                       grounding_px=768, identity_strength=.8,
                       generation_loras=[["style.safetensors",.4],["detail.safetensors",-.3]])
        self.assertEqual(g["11"]["inputs"]["seed"], 73)
        self.assertEqual(g["10"]["inputs"]["width"], 768)
        self.assertEqual(g["7"]["inputs"]["ref_boost"], .6)
        self.assertEqual(g["8"]["inputs"]["grounding_px"], 768)
        self.assertEqual(g["4"]["inputs"]["strength_model"], .8)
        self.assertEqual(g["identity_extra_0"]["inputs"]["model"], ["4",0])
        self.assertEqual(g["identity_extra_1"]["inputs"]["model"], ["identity_extra_0",0])
        self.assertEqual(g["7"]["inputs"]["model"], ["identity_extra_1",0])

    def test_invalid_controls_rejected_before_gpu(self):
        for kw in [dict(image_path=""),dict(prompt=" "),dict(seed=-1),dict(seed=1.5),
                   dict(width=513),dict(height=256),dict(width=2048,height=2048),
                   dict(steps=0),dict(ref_boost=float("nan")),dict(grounding_px=10),
                   dict(identity_strength=float("inf")),dict(seed=True),
                   dict(generation_loras=[[IDENTITY_LORA,1]]),
                   dict(generation_loras=[["x",1]]*9)]:
            with self.subTest(kw=kw), self.assertRaises(ValueError): self.graph(**kw)

    def test_secure_identity_mode_selects_the_init_image_role(self):
        tree = ast.parse((ROOT/"handler.py").read_text())
        wanted = {"task_mode_values", "task_mode", "is_openpose_extract", "is_identity_edit",
                  "is_i2i", "secure_image_roles", "secure_condition_image"}
        assignments = [node for node in ast.walk(tree)
                       if isinstance(node, ast.Assign) and len(node.targets) == 1
                       and isinstance(node.targets[0], ast.Name)
                       and node.targets[0].id in wanted]
        scope = {"job_input": {"mode": "identity_edit", "task": "identity_edit",
                              "task_type": "identity_edit"},
                 "get_secure_media_input": Mock(return_value="source.png")}
        exec(compile(ast.Module(body=sorted(assignments, key=lambda n: n.lineno),
                                type_ignores=[]), "routing", "exec"), scope)
        self.assertTrue(scope["is_identity_edit"])
        self.assertFalse(scope["is_i2i"])
        self.assertIn("init_image", scope["secure_image_roles"])
        self.assertEqual(scope["secure_condition_image"], "source.png")

    def test_secure_identity_settings_survive_decryption(self):
        tree = ast.parse((ROOT/"handler.py").read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name=="decrypt_secure_input")
        scope = {"decrypt_structured_envelope": Mock(return_value={"prompt":"same character", "identity_edit":{"ref_boost":.7}})}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),"handler.py","exec"),scope)
        data = scope["decrypt_secure_input"]({"_secure":{"wrapped_key":"test","binding":{"model_id":"krea2-turbo"}}})
        self.assertEqual(data["identity_edit"],{"ref_boost":.7})
        self.assertNotIn("_secure",data)


if __name__ == "__main__": unittest.main()
