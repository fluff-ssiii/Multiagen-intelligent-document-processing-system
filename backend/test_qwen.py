from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration
import torch

# 1. Load the processor and model
# Automatically downloads weights to your local huggingface cache (~/.cache/huggingface)
model_id = "Qwen/Qwen2.5-VL-7B-Instruct"

processor = AutoProcessor.from_pretrained(model_id)

# Load with device_map="auto" to automatically utilize your GPU
model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
    model_id, 
    torch_dtype=torch.bfloat16, # Use torch.float16 if your GPU doesn't support bfloat16
    device_map="auto"
)

print("Qwen2.5-VL-7B loaded successfully!")