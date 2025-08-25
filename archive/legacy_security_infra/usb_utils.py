import os

def find_usb_mount_by_label(label="BW_PW_USB", test_file=None):
    """
    label: USB의 Volume Label
    test_file: 해당 파일이 있어야만 성공으로 간주 (ex: 'bw_pw_user1.txt')
    return: 마운트 경로(예: '/mnt/d/'), 없으면 None
    """
    label_path = f"/dev/disk/by-label/{label}"
    if os.path.exists(label_path):
        device = os.path.realpath(label_path)
        with os.popen(f"df | grep {device}") as f:
            for line in f:
                fields = line.split()
                if len(fields) > 5:
                    mnt = fields[5]
                    if test_file is None or os.path.exists(os.path.join(mnt, test_file)):
                        return mnt
    # WSL2/Windows 대응
    for d in "abcdefghijklmnopqrstuvwxyz":
        mnt = f"/mnt/{d}/"
        if os.path.exists(mnt) and os.path.isdir(mnt):
            try:
                files = os.listdir(mnt)
                if test_file is None or test_file in files:
                    return mnt
            except Exception:
                continue
    return None
