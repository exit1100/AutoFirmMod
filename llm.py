from langchain_openai import OpenAIEmbeddings
from langchain_openai import ChatOpenAI


def get_llm(model='gpt-4o'):
    llm = ChatOpenAI(model=model)
    return llm

def get_llm_response(tree_path):
    llm = get_llm()
    with open(tree_path, "r") as file:
        directory_structure = file.read()
    system_prompt = (
        "다음은 파일 시스템의 디렉토리 구조입니다. 각 디렉토리와 파일에 대한 정보를 바탕으로 질문에 답변해 주세요.\n"
        "디렉토리 구조:\n"
        f"{directory_structure}\n\n"
        "질문: 이 파일 시스템에서 특정 파일이나 설정 위치를 찾아야 합니다. "
        "`passwd` 파일, `shadow` 파일, 그리고 부팅 시 실행되는 스크립트의 경로를 각각 찾아 딕셔너리 형태로 답변해 주세요. "
        "답변 시 문자열을 제외하고 딕셔너리 형태로 답변해야만 합니다."
    )

    response = llm(system_prompt)
    return response.content
