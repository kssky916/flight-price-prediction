import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR))

from src.llm_client import parse_travel_request


text = "10월1일~10월10일이 휴가 기간이고 한 3박4일 일본여행을 가고싶어"

result = parse_travel_request(text)

print(result)