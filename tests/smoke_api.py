import pymupdf
from fastapi.testclient import TestClient

from app.main import app


def main() -> None:
    payload = {
        "offer_text": (
            "Data Engineer at Example Company. We need Python, SQL, Databricks, "
            "PySpark, Azure, ETL, data modeling, APIs and cloud architecture. "
            "The role is based in Paris and works with analytics teams."
        ),
        "preferred_language": "en",
        "source": "Test",
    }
    with TestClient(app) as client:
        response = client.post("/api/applications/generate", json=payload)
        print("generate", response.status_code)
        assert response.status_code == 200, response.text
        application = response.json()
        for kind in ("cv", "letter"):
            document = client.get(f"/api/applications/{application['id']}/{kind}")
            pdf = pymupdf.open(stream=document.content, filetype="pdf")
            page_count = len(pdf)
            print(kind, document.status_code, len(document.content), page_count)
            assert document.status_code == 200
            assert page_count == 1
            if kind == "cv":
                page = pdf[0]
                lowest_text = max(
                    block[3]
                    for block in page.get_text("blocks")
                    if block[4].strip()
                )
                fill_ratio = lowest_text / page.rect.height
                print("cv_fill", round(fill_ratio, 3))
                assert 0.93 <= fill_ratio <= 0.97
        workbook = client.get("/api/export.xlsx")
        print("excel", workbook.status_code, len(workbook.content))
        assert workbook.status_code == 200


if __name__ == "__main__":
    main()
