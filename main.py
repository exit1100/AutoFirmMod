import streamlit as st
import os
import uuid
import subprocess
from dotenv import load_dotenv
from llm import get_llm_response
import json

load_dotenv()
UPLOAD_DIR = "upload"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def save_uploaded_file(upload_file, user_id):
    user_dir = os.path.join(UPLOAD_DIR, user_id)
    os.makedirs(user_dir, exist_ok=True)

    save_path = os.path.join(user_dir, upload_file.name)
    with open(save_path, "wb") as f:
        f.write(upload_file.getbuffer())
    return save_path, user_dir


def run_binwalk(file_path, log_path):
    with open(log_path, "w") as log_file:
        subprocess.run(["binwalk", save_path], stdout=log_file, stderr=log_file)


def extract_squashfs(file_path, offset, size, output_path):
    subprocess.run([
        "dd",
        f"if={file_path}",
        f"of={output_path}",
        "bs=1",
        f"skip={offset}",
        f"count={size}"
    ], check=True)


def extract_filesystem(squashfs_path, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    subprocess.run(["unsquashfs", "-f", "-d", output_dir, squashfs_path], check=True)
    return


def directory_clean(path):
    if os.path.exists(path):
        subprocess.run(["rm", "-rf", path], check=True)


def directory_tree(user_dir, save_dir):
    with open(save_dir, "w") as save_dir:
        subprocess.run(
            f"tree {user_dir}/rootfs| sed 's|{user_dir.replace("/", "\\/")}/||'",
            shell=True, stdout=save_dir, stderr=save_dir
        )


# Streamlit Main
st.title("AutoFirmMod")

upload_file = st.file_uploader("Please upload your firmware", type=["bin"])

if upload_file is not None:
    user_id = str(uuid.uuid4())
    directory_clean(f'{UPLOAD_DIR}/{user_id}')
    save_path, user_dir = save_uploaded_file(upload_file, user_id)
    log_path = os.path.join(user_dir, "binwalk_log.txt")
    run_binwalk(save_path, log_path)
    
    st.success(f"File saved successfully : {upload_file.name}")
    st.success(f"Running Binwalk on uploaded file...")

    squashfs_lines = []
    with open(log_path, "r") as f:
        lines = f.readlines() 

        for i, line in enumerate(lines):
            if "squashfs" in line.lower():
                current_line = line.strip().split()
                squashfs_lines.append(current_line) 
                if i + 1 < len(lines) and "squashfs" not in lines[i + 1].lower():
                    next_line = lines[i + 1].strip().split()
                    squashfs_lines.append(next_line)

    cnt = 0
    if not squashfs_lines:
        st.info("squashfs Filesystem not found.")
    else:
        st.success("squashfs Filesystem found.")
        for i in range(len(squashfs_lines)):
            if squashfs_lines[i][2].lower() == 'squashfs':
                offset = int(squashfs_lines[i][0])
                size = int(squashfs_lines[i+1][0]) - int(squashfs_lines[i][0])
                extract_squashfs(save_path, offset, size, user_dir+f'/squashfs{cnt}.bin')  
                cnt += 1

        os.makedirs(f'{user_dir}/rootfs', exist_ok=True) 
        for i in range(cnt):
            input_squashfs = f'{user_dir}/squashfs{i}.bin'
            output_dir = f'{user_dir}/rootfs/squashfs-root-{i}'
            extract_filesystem(input_squashfs, output_dir)
            st.success(f"Filesystem extraction completed : squashfs-root-{i}")

        directory_tree(f'{user_dir}', f'{user_dir}/tree')

        response_data = json.loads(get_llm_response(f'{user_dir}/tree'))
        print(response_data)
        #response_data = { "passwd": "rootfs/squashfs-root-0/etc/passwd", "shadow": "rootfs/squashfs-root-0/etc/shadow", "boot_script": "rootfs/squashfs-root-0/etc/init.d/rcS" }
        st.write("### boot script & passwd")
        st.write(response_data)
        for i in response_data:
            st.success(f'{i} : {response_data[i]}')

