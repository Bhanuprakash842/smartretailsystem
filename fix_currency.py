import os
import re

dirs = ['templates', 'chatbot', 'tests', 'documents', 'forecasting']
files_to_process = ['app.py', 'models.py']

for d in dirs:
    for dp, dn, filenames in os.walk(d):
        for f in filenames:
            if f.endswith('.html') or f.endswith('.py') or f.endswith('.txt'):
                files_to_process.append(os.path.join(dp, f))

for filepath in files_to_process:
    if not os.path.exists(filepath):
        continue
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Safe replacements for currency
    new_content = re.sub(r'\$\{\{', '₹{{', content)
    new_content = re.sub(r'\$([0-9])', r'₹\1', new_content)
    new_content = new_content.replace('Price ($)', 'Price (₹)')
    new_content = new_content.replace("'$'", "'₹'")
    new_content = new_content.replace('"$"', '"₹"')
    new_content = new_content.replace('with $ sign', 'with ₹ sign')
    new_content = new_content.replace('$$', '₹$')  # Javascript: $${var} -> ₹${var}
    
    if content != new_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print('Updated', filepath)

print('Done')
