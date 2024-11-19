from langchain_openai import ChatOpenAI


def get_llm(model='gpt-4o'):
    llm = ChatOpenAI(model=model)
    return llm


def search_file_prompt(flag, tree_path=None) :
    with open(tree_path, "r") as file:
        directory_structure = file.read()
    check_file_list = ''
    if flag == 1:
        check_file_list = "`passwd` 파일, `shadow` 파일, 그리고 부팅 스크립트의 경로를 각각 찾아 JSON 형태로 답변해 주세요."
    elif flag == 2:
        check_file_list = "`telnetd` 파일, `nc` 파일, `socat` 파일, 그리고 `busybox`의 경로를 각각 찾아 JSON 형태로 답변해 주세요."

    system_prompt = (
        "다음은 파일 시스템의 디렉토리 구조입니다. 각 디렉토리와 파일에 대한 정보를 바탕으로 질문에 답변해 주세요.\n"
        "디렉토리 구조:\n"
        f"{directory_structure}\n\n"
        "질문: 이 파일 시스템에서 특정 파일이나 위치를 찾아야 합니다. "
        f"{check_file_list}"
        "JSON 형식으로만 답변하고, 그 외의 문구나 코드 블록(```)을 포함하지 마세요."
        "경로를 나타낼땐 최상단 디렉토리부터 표시해주시고, 심볼릭 링크는 포함하지 마세요."
        "만약 경로에 파일이 없는 경우 null로 표현해주세요."
    )
    return system_prompt


def target_file_path_prompt(setting_path, binary_path, user_dir) :
    system_prompt = (
        "다음은 파일 시스템의 주요 구조입니다. 각 디렉토리와 경로에 대한 정보를 바탕으로 질문에 답변해 주세요.\n"
        "정보:\n"
        f"settings_path = {setting_path}\n"
        f"binary_path = {binary_path}\n\n"
        "질문: 정보를 참고하여 부팅 스크립트에 telnetd를 백그라운드로 실행하는 명령어를 echo로 추가해주시고, shadow 파일의 root 계정 비밀번호를 sed -i 's/^root:[^:]*:/root::/' 명령어로 제거해주세요."
        "파이썬 리스트 형태로 답변해주시고, 대부분의 경로를 생략하지마세요."
        "telnetd 는 마운트 된 이후 경로를 써야하므로 앞에 파일 시스템 경로는 생략해주세요."
        f"값을 쓰는 파일의 경로는 앞에 {user_dir}/ 경로를 추가해야 합니다."
        "그 외의 문구나 코드 블록(```)을 포함하지 마세요."
        ""
    )
    return system_prompt


def get_llm_response(flag, tree_path=None, setting_path=None, binary_path=None, user_dir=None):
    llm = get_llm()
    if flag == 1 or flag == 2:
        system_prompt = search_file_prompt(flag, tree_path)
    elif flag == 3:
        system_prompt = target_file_path_prompt(setting_path, binary_path, user_dir)
    response = llm(system_prompt)
    return response.content
