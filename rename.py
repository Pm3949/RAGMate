import os
import re

directory = '/home/mp3949/Documents/RAGMate'
exclude_dirs = {'.git', 'node_modules', '__pycache__', 'env', 'venv', '.next', 'build', 'dist', '.gemini'}

for root, dirs, files in os.walk(directory):
    dirs[:] = [d for d in dirs if d not in exclude_dirs]
    for file in files:
        if file.endswith(('.js', '.jsx', '.ts', '.tsx', '.html', '.json', '.py', '.md')):
            filepath = os.path.join(root, file)
            # Skip the script itself
            if filepath == os.path.abspath(__file__):
                continue
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                new_content = content
                
                # Careful replacements
                # First, temporarily mask the root directory path to avoid breaking it
                root_path_mask = "###ROOT_DIR_MASK###"
                new_content = new_content.replace('/home/mp3949/Documents/RAGMate', root_path_mask)
                
                # Replace variations
                new_content = new_content.replace('RAGMate', 'BlinkBot')
                new_content = new_content.replace('RagMate', 'BlinkBot')
                new_content = new_content.replace('ragmate', 'blinkbot')
                
                # Unmask the root directory
                new_content = new_content.replace(root_path_mask, '/home/mp3949/Documents/RAGMate')
                
                if new_content != content:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    print(f"Updated {filepath}")
            except Exception as e:
                print(f"Error processing {filepath}: {e}")
