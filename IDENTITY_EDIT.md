# Krea2 Identity Edit

The `identity_edit` mode is a separate, reference-conditioned workflow for Dataset Studio. Existing text-to-image and denoising i2i remain unchanged. It uses an empty target latent, the identity adapter, grounded encoding, CFG 1 and the original source image. It is not ordinary low-denoise i2i.

Send `mode`, `task` and `task_type` consistently as `identity_edit`. The secure transport accepts the source under `init_image`, `source_image` or `image`. Put identity controls inside the encrypted structured payload as `identity_edit`: `grounding_px` (512–1536), `ref_boost` (0–10), `identity_strength` (0–1.5). Studio snapshots its configured controls; omitted worker defaults are 512, 0.25 and 1. Steps: 1–50. Dimensions: multiples of 64, 512–2048 on each side, at most 2 MP.

The Docker image includes the pinned `comfyui-krea2edit` node implementation and `conradlocke/krea2-identity-edit` v1.2 adapter. The adapter SHA-256 is checked during build, and its license and notice are stored in `/licenses/krea2-identity`. Startup downloads and a persistent model-cache volume are not required. The target latent is wired to the patch node so reference fitting happens before sampling.

This path uses ordinary RunPod jobs, not RunPod Batch Jobs. Queueing several dataset candidates does not promise a single warm GPU worker. CPU checks validate graph construction, control validation, secure source routing and unchanged i2i behavior; GPU validation is still required after an image build.
