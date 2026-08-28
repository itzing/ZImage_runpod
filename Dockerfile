# Use specific version of nvidia cuda image
FROM wlsdml1114/multitalk-base:1.4 as runtime

# wget 설치 (URL 다운로드를 위해)
RUN apt-get update && apt-get install -y wget && rm -rf /var/lib/apt/lists/*

RUN pip install -U "huggingface_hub[hf_transfer]"
RUN pip install runpod websocket-client boto3 cryptography

WORKDIR /


RUN git clone https://github.com/comfyanonymous/ComfyUI.git && \
    cd /ComfyUI && \
    pip install -r requirements.txt

RUN cd /ComfyUI/custom_nodes && \
    git clone https://github.com/Comfy-Org/ComfyUI-Manager.git && \
    cd ComfyUI-Manager && \
    pip install -r requirements.txt

RUN mkdir -p /ComfyUI/models/diffusion_models /ComfyUI/models/text_encoders /ComfyUI/models/vae /ComfyUI/models/loras && \
    wget https://huggingface.co/Comfy-Org/Krea-2/resolve/main/split_files/diffusion_models/krea2_turbo_fp8_scaled.safetensors -O /ComfyUI/models/diffusion_models/krea2_turbo_fp8_scaled.safetensors && \
    wget https://huggingface.co/Comfy-Org/Krea-2/resolve/main/split_files/text_encoders/qwen3vl_4b_fp8_scaled.safetensors -O /ComfyUI/models/text_encoders/qwen3vl_4b_fp8_scaled.safetensors && \
    wget https://huggingface.co/Comfy-Org/Krea-2/resolve/main/split_files/vae/qwen_image_vae.safetensors -O /ComfyUI/models/vae/qwen_image_vae.safetensors


COPY . .
RUN mkdir -p /ComfyUI/user/default/ComfyUI-Manager
COPY config.ini /ComfyUI/user/default/ComfyUI-Manager/config.ini
COPY extra_model_paths.yaml /ComfyUI/extra_model_paths.yaml
RUN chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]
