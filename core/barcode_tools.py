import qrcode

def generate_qr(data, output_path):
    img = qrcode.make(data)
    img.save(output_path)
