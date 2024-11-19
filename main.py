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


def extract_squashfs(file_path, output_path, offset, size=None):
    command = [
        "dd",
        f"if={file_path}",
        f"of={output_path}",
        "bs=1",
        f"skip={offset}"
    ]
    if size is not None:
        command.append(f"count={size}")
    subprocess.run(command, check=True)


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

def button_click_callback(key):
    st.session_state.button_clicked = key


# Streamlit Main
st.title("AutoFirmMod")
st.markdown("""
        <style>
        .button-container {
            display: flex;
            justify-content: center;
            width: 100%;
        }
        .stButton button {
            width: 100px; 
        }
        </style>
    """, unsafe_allow_html=True)

if "button_clicked" not in st.session_state:
    st.session_state.button_clicked = None

if "file_paths_json1" not in st.session_state:
    st.session_state.file_paths_json1 = None

if "file_paths_json2" not in st.session_state:
    st.session_state.file_paths_json2 = None


if st.session_state.button_clicked is None:
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
                if squashfs_lines[i] and squashfs_lines[i][2].lower() == 'squashfs':
                    offset = int(squashfs_lines[i][0])
                    if not squashfs_lines[i+1]:
                        size = None
                    else:
                        size = int(squashfs_lines[i+1][0]) - int(squashfs_lines[i][0])
                    output_path = user_dir+f'/squashfs{cnt}.bin'
                    extract_squashfs(save_path, output_path, offset, size)  
                    cnt += 1

            os.makedirs(f'{user_dir}/rootfs', exist_ok=True) 
            for i in range(cnt):
                input_squashfs = f'{user_dir}/squashfs{i}.bin'
                output_dir = f'{user_dir}/rootfs/squashfs-root-{i}'
                extract_filesystem(input_squashfs, output_dir)
                st.success(f"Filesystem extraction completed : squashfs-root-{i}")

            directory_tree(f'{user_dir}', f'{user_dir}/tree')

            #file_paths = get_llm_response(1, f'{user_dir}/tree')
            #file_paths_json1 = json.loads(file_paths)
            file_paths_json1 = {"passwd":"rootfs/squashfs-root-0/etc/config/passwd","shadow":"rootfs/squashfs-root-0/etc/config/shadow","boot_scripts":["rootfs/squashfs-root-0/etc/init.d/rc.local","rootfs/squashfs-root-0/etc/init.d/rcS"]}
            st.session_state.file_paths_json1 = file_paths_json1

            st.write("### boot script & passwd")
            st.write(file_paths_json1)
            for key, path in file_paths_json1.items():
                try:
                    if isinstance(path, list):
                        for single_path in path:
                            with open(f'{user_dir}/{single_path}', 'r') as file:
                                content = file.read()
                                st.write(f"### {single_path}")
                                st.code(content)
                                st.markdown("---")
                    else:
                        with open(f'{user_dir}/{path}', 'r') as file:
                            content = file.read()
                            st.write(f"### {path}:")
                            st.code(content)
                        st.markdown("---")
                except FileNotFoundError:
                    st.info(f"File {path} not found.")
                except Exception as e:
                    print(f"An error occurred while reading {path}: {e}")

            #file_paths = get_llm_response(2, f'{user_dir}/tree')
            #file_paths_json2 = json.loads(file_paths)
            file_paths_json2 = {"telnetd":"rootfs/squashfs-root-1/sbin/telnetd","nc":"rootfs/squashfs-root-1/bin/nc","socat":None,"busybox":None}
            st.session_state.file_paths_json2 = file_paths_json2
            st.write("### Backdoor Point List")
            
        
            st.write(file_paths_json2)
            st.markdown("---")

            st.write("### Choice Backdoor")
            columns = st.columns(4) 
            for idx, (key, path) in enumerate(file_paths_json2.items()):
                with columns[idx]:
                    st.markdown('<div class="button-container">', unsafe_allow_html=True)
                    if path is None:
                        st.button(f"{key}", key=f"{key}_disabled", disabled=True, help="Not Available")
                    else:
                        st.button(
                            f"{key}", 
                            key=f"{key}_enabled", 
                            disabled=False, 
                            help="Available",
                            on_click=button_click_callback,
                            args=(key,) 
                        )
                    st.markdown('</div>', unsafe_allow_html=True)
                

if st.session_state.get("button_clicked"):
    st.markdown(f"### Backdoor Type : {st.session_state.button_clicked}")
    if st.session_state.button_clicked == "telnetd":
        st.code(f"file_paths_json1: {st.session_state.file_paths_json1}")
        st.code(f"file_paths_json2: {st.session_state.file_paths_json2}")
    elif st.session_state.button_clicked == "nc":
        st.code(f"file_paths_json1: {st.session_state.file_paths_json1}")
        st.code(f"file_paths_json2: {st.session_state.file_paths_json2}")
    elif st.session_state.button_clicked == "socat":
        st.code(f"file_paths_json1: {st.session_state.file_paths_json1}")
        st.code(f"file_paths_json2: {st.session_state.file_paths_json2}")
    elif st.session_state.button_clicked == "busybox":
        st.code(f"file_paths_json1: {st.session_state.file_paths_json1}")
        st.code(f"file_paths_json2: {st.session_state.file_paths_json2}")

