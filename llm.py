from langchain_openai import ChatOpenAI


def get_llm(model='gpt-4o'):
    llm = ChatOpenAI(model=model)
    return llm


def handle_prompt(flag, tree_path=None) :
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
    )
    return system_prompt


def get_llm_response(flag, tree_path=None):
    llm = get_llm()
    system_prompt = handle_prompt(flag, tree_path)
    response = llm(system_prompt)
    return response.content