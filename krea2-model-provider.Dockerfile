FROM alpine:3.20

RUN apk add --no-cache ca-certificates wget

RUN mkdir -p \
      /models/diffusion_models \
      /models/text_encoders \
      /models/vae

RUN wget --progress=dot:giga \
      "https://huggingface.co/Comfy-Org/Krea-2/resolve/main/diffusion_models/krea2_turbo_fp8_scaled.safetensors?download=true" \
      -O /models/diffusion_models/krea2_turbo_fp8_scaled.safetensors

RUN wget --progress=dot:giga \
      "https://huggingface.co/Comfy-Org/Krea-2/resolve/main/text_encoders/qwen3vl_4b_fp8_scaled.safetensors?download=true" \
      -O /models/text_encoders/qwen3vl_4b_fp8_scaled.safetensors

RUN wget --progress=dot:giga \
      "https://huggingface.co/Comfy-Org/Krea-2/resolve/main/vae/qwen_image_vae.safetensors?download=true" \
      -O /models/vae/qwen_image_vae.safetensors
