"""Kalıcılık katmanı — dosya okuma/yazma YALNIZCA burada olur.

Servisler ve API bu sınıflardan geçer; `open()` çağrısı başka hiçbir katmanda
bulunmaz. Eşzamanlılık için tek bir `threading.Lock` var
(`state_repo.LOCK`) — tur akışı bugünkü gibi seri kalsın.
"""
