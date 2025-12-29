import os

def get_available_filename(directory: str, filename: str) -> str:
    """
    ถ้าไฟล์ซ้ำ → เปลี่ยนเป็น filename(1).ext, filename(2).ext
    """
    name, ext = os.path.splitext(filename)
    counter = 1
    new_filename = filename

    while os.path.exists(os.path.join(directory, new_filename)):
        new_filename = f"{name}({counter}){ext}"
        counter += 1

    return new_filename
