# Use specific version of nvidia cuda image
FROM itzing/krea2-turbo-models:v1 AS krea2_model_provider
FROM wlsdml1114/multitalk-base:1.4 AS runtime

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

RUN mkdir -p /ComfyUI/models/diffusion_models /ComfyUI/models/text_encoders /ComfyUI/models/vae /ComfyUI/models/loras
COPY --from=krea2_model_provider /models/diffusion_models/krea2_turbo_fp8_scaled.safetensors /ComfyUI/models/diffusion_models/krea2_turbo_fp8_scaled.safetensors
COPY --from=krea2_model_provider /models/text_encoders/qwen3vl_4b_fp8_scaled.safetensors /ComfyUI/models/text_encoders/qwen3vl_4b_fp8_scaled.safetensors
COPY --from=krea2_model_provider /models/vae/qwen_image_vae.safetensors /ComfyUI/models/vae/qwen_image_vae.safetensors


# Identity Edit assets are installed at image build, never on GPU worker startup.
# Preserve the model stage/cache and pin the compatible node implementation.
RUN git clone https://github.com/lbouaraba/comfyui-krea2edit.git /ComfyUI/custom_nodes/comfyui-krea2edit && \
    cd /ComfyUI/custom_nodes/comfyui-krea2edit && \
    git checkout 13ef60f20828949becada815d3cbc371eb5ccaab
RUN mkdir -p /ComfyUI/models/loras/krea /licenses/krea2-identity && \
    wget -q -O /ComfyUI/models/loras/krea/krea2_identity_edit_v1_2.safetensors \
    https://huggingface.co/conradlocke/krea2-identity-edit/resolve/f33b26291c640e8ec50b0da420bfee3c9a660daa/krea2_identity_edit_v1_2.safetensors && \
    echo "6adf9a69cc9502d286db7b69964d37da7e9cfe4b05b4d004bc275f087d3fd3cf  /ComfyUI/models/loras/krea/krea2_identity_edit_v1_2.safetensors" | sha256sum -c - && \
    wget -q -O /licenses/krea2-identity/LICENSE.pdf https://huggingface.co/conradlocke/krea2-identity-edit/resolve/f33b26291c640e8ec50b0da420bfee3c9a660daa/LICENSE.pdf && \
    wget -q -O /licenses/krea2-identity/NOTICE https://huggingface.co/conradlocke/krea2-identity-edit/resolve/f33b26291c640e8ec50b0da420bfee3c9a660daa/NOTICE

# Pinned regional LoRA runtime, baked into the existing endpoint image.
RUN git clone https://github.com/januspluto/ComfyUI-Krea2-Regional.git /ComfyUI/custom_nodes/ComfyUI-Krea2-Regional && \
    cd /ComfyUI/custom_nodes/ComfyUI-Krea2-Regional && \
    git checkout e88207aea47ccefc47605def2dc4f727e3e5f6c6

COPY . .
RUN mkdir -p /ComfyUI/user/default/ComfyUI-Manager
COPY config.ini /ComfyUI/user/default/ComfyUI-Manager/config.ini
COPY extra_model_paths.yaml /ComfyUI/extra_model_paths.yaml
RUN chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]
