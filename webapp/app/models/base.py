"""Model tabanı: JSON sözlüğüne BİREBİR geri dönüş.

`data/state.json` devam eden gerçek bir oyunun kaydı — bir alanı tanımıyor
olmamız onu atmak için sebep değil. Bu yüzden her model iki şey taşır:

  * `extra`     — modelin tanımadığı alanlar, olduğu gibi geri yazılır
  * `key_order` — kayıtta görülen anahtar sırası; aynı zamanda "bu alan
                  kayıtta VARDI" işaretidir (boş liste/sözlük de yazılsın diye)

`to_dict()` önce bu sırayı uygular, sonra sonradan doğan alanları kanonik
sıralarında ekler. Böylece yükle-kaydet turu dosyada tek karakter oynatmaz.
"""


class DictModel:
    """`from_dict` / `to_dict` çifti olan modellerin ortak gövdesi.

    Alt sınıflar `extra` ve `key_order` alanlarını tanımlar (dataclass alanı
    olarak, en sonda) ve tanıdıkları alan adlarını `KNOWN` demetinde sayar.
    """

    KNOWN: tuple = ()

    def _touch(self, key: str) -> None:
        """`dict.setdefault(key, ...)` karşılığı: alanı 'kayıtta var' say."""
        if key not in self.key_order:
            self.key_order.append(key)

    def _set(self, key: str, value) -> None:
        """Alanı yaz ve kayıtta var olarak işaretle."""
        setattr(self, key, value)
        self._touch(key)

    def _emit(self, values: dict) -> dict:
        """`values` kanonik sırada verilir; çıktı önce KAYNAKTAKİ sırayı,
        sonra kanonik sırayı izler. Tanınmayan alanlar da yerinde kalır.

        Bir alan ancak kayıtta vardıysa ya da gerçekten bir değer taşıyorsa
        yazılır — yoksa `wounds: []` gibi alanlar hiç sahip olmadıkları eski
        kayıtlara sessizce eklenirdi."""
        known = {k: v for k, v in values.items() if k in self.key_order or v}
        out = {}
        for key in self.key_order:
            if key in known:
                out[key] = known[key]
            elif key in self.extra:
                out[key] = self.extra[key]
        for key, value in known.items():
            out.setdefault(key, value)
        for key, value in self.extra.items():
            out.setdefault(key, value)
        return out

    @classmethod
    def _split(cls, data: dict):
        """(extra, key_order) — tanınmayan alanları ve özgün sırayı ayırır."""
        data = data or {}
        extra = {k: v for k, v in data.items() if k not in cls.KNOWN}
        return extra, list(data.keys())
