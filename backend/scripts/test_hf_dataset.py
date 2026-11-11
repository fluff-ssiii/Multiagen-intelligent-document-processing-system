
from datasets import load_dataset

DATASET_NAME = "processvenue/INVOICE_ANNOTATION_V2"

print("Loading dataset...")

dataset = load_dataset(
    DATASET_NAME,
    split="train",
    streaming=True
)

print("\nDataset loaded!")

for index, sample in enumerate(dataset):
    print(f"\n========== SAMPLE {index + 1} ==========")

    for key, value in sample.items():
        print(f"\nColumn: {key}")
        print("Type:", type(value).__name__)

        # Image column
        if hasattr(value, "size") and hasattr(value, "mode"):
            print("Image size:", value.size)
            print("Image mode:", value.mode)

        # Annotation / text columns
        else:
            print("Value:", str(value)[:500])

    if index == 2:
        break

print("\nInspection completed.")

print("\nALL DATASET COLUMNS:")
print(dataset.features)

sample = next(iter(dataset))

print("\nSAMPLE KEYS:")
print(sample.keys())