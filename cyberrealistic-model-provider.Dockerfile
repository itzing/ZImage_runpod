FROM python:3.12-slim

RUN pip install --no-cache-dir "huggingface_hub[hf_transfer]"

ENV HF_HUB_ENABLE_HF_TRANSFER=1

RUN mkdir -p /models/unet && \
    python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='itzing/mpm-test', filename='cyberrealisticZImage_v60.safetensors', local_dir='/models/unet', local_dir_use_symlinks=False)" && \
    mv /models/unet/cyberrealisticZImage_v60.safetensors /models/unet/z_image_turbo_bf16.safetensors
