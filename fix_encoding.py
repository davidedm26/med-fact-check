import os

files = [
    r"b:\Workspace\Unina-MSc\BIG-DATA\med-fact-check\app\frontend\components\ui_components.py",
    r"b:\Workspace\Unina-MSc\BIG-DATA\med-fact-check\app\frontend\pages\Fact_Check.py",
    r"b:\Workspace\Unina-MSc\BIG-DATA\med-fact-check\app\frontend\utils\text_processing.py"
]

for file in files:
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()
    with open(file, 'w', encoding='utf-8-sig') as f:
        f.write(content)
print("Saved with UTF-8 BOM")
