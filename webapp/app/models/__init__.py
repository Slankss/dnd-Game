"""Alan modelleri — SAF Python.

Bu katman Flask bilmez, dosya açmaz, ağa çıkmaz; sadece stdlib kullanır.
Her sınıf `from_dict()` / `to_dict()` çiftiyle `data/state.json`'daki biçime
BİREBİR dönüşür: devam eden gerçek bir oyun var (Gün 98+), kayıt formatı
değişmiyor. Tanınmayan alanlar ve anahtar sırası bile korunur (bkz. base.py).
"""
