"""Modele giden metin blokları.

Anlatıcıya her turda verilen "defter" burada kurulur: kadro, sahne katılımı,
envanter, yaralar, göstergeler, görünür zaman çizelgesi ve tur sonu
hatırlatması. Hepsi world_state SÖZLÜĞÜ üzerinde çalışır (WorldState.to_dict()
çıktısı) — model nesnelerine bağlanmadıkları için prompt metni değiştikçe
alan katmanına dokunmak gerekmez.
"""

import re

from app.models.conditions import describe_when
from app.models.person import SECRET_FIELD
from app.models.presence import PRESENCE_LABELS, canon_presence
from app.models.vitals import vital_label


# Kadro yardımcıları — WorldState'in aynı adlı metotlarının sözlük üzerinde
# çalışan karşılıkları. Buradaki bloklar ham sözlükle çalıştığı için gerekli.
def _alive_players(world_state: dict) -> list:
    return [
        name
        for name, info in (world_state.get("characters") or {}).items()
        if info.get("alive", True)
    ]


def _presence_of(info: dict) -> dict:
    presence = info.get("presence")
    presence = presence if isinstance(presence, dict) else {}
    state = canon_presence(presence.get("state")) or "sahnede"
    return {**presence, "state": state}


def _present_players(world_state: dict) -> list:
    return [
        name
        for name, info in (world_state.get("characters") or {}).items()
        if info.get("alive", True) and _presence_of(info)["state"] == "sahnede"
    ]


def _absent_players(world_state: dict) -> list:
    out = []
    for name, info in (world_state.get("characters") or {}).items():
        if not isinstance(info, dict) or not info.get("alive", True):
            continue
        presence = _presence_of(info)
        if presence["state"] != "sahnede":
            out.append((name, presence))
    return out


def world_dice_note(entry: dict) -> str:
    return (
        f"DÜNYA ZARI (GİZLİ — oyunculara ASLA gösterme, metninde ondan söz etme): "
        f"{entry['roll']} ({entry['band']}) — {entry['hint']}.\n"
        "Bu zar oyuncunun hamlesinden BAĞIMSIZ olarak dünyanın bu turda ne "
        "yaptığını belirler: aktif `challenges` kayıtlarının clock/progress/"
        "severity değerlerini bu banda göre ilerlet ya da sabit tut ve "
        "state-update ile kaydet."
    )


# --------------------------------------------------------------- scenario.json
# scenario.py'deki değerler varsayılandır. data/scenario_override.json varsa
# (arayüzden "senaryo içe aktar" ile yüklenir) onun içeriği önceliklidir —
# server.py'yi yeniden başlatmadan senaryo değiştirilebilir.



def visible_timeline_note(log: list, limit: int = 6) -> str:
    """Oyunculara FİİLEN gösterilmiş son akış. İki kanal (oyuncu sohbeti +
    anlatıcı kanalı) aynı Claude oturumunu paylaşıyor; bu blok olmadan model
    bazen hikayeyi, oyuncuların hiç görmediği GM onay mesajından devam
    ettiriyor ve iki taraf birbirini tutmuyordu."""
    lines = ["OYUNCULARIN EKRANINDA GÖRÜNEN SON AKIŞ (hikaye buradan devam eder):"]
    for entry in (log or [])[-limit:]:
        role = entry.get("role")
        text = (entry.get("text") or "").strip().replace("\n", " ")
        if role == "user":
            roll = ""
            if entry.get("roll") is not None:
                roll = f" (ZAR {entry['roll']} - {entry.get('band')})"
            lines.append(f"[{entry.get('player', '?')}{roll}] {text[:300]}")
        elif role == "system":
            lines.append(f"[SİSTEM] {text[:300]}")
        else:
            lines.append(f"[ANLATICI] {text[:600]}")
    if len(lines) == 1:
        lines.append("(henüz gösterilmiş bir sahne yok)")
    lines.append(
        "ÖNEMLİ — İKİ KANAL TEK HİKAYE: konuşma geçmişinde `[ANLATICI NOTU - "
        "GİZLİ]` etiketli mesajlar ve onlara verdiğin kısa onaylar olabilir. "
        "Bunlar oyuncuların GÖRMEDİĞİ ayrı bir yönetim kanalıdır — hikayeyi o "
        "onaylardan değil, YUKARIDAKİ oyuncu akışından devam ettir ve "
        "oyunculara görmedikleri bir şeye atıfta bulunma. `[ANLATICI MÜDAHALESİ "
        "- ...]` etiketiyle yayınlanan sahneler ise oyuncuların gördüğü akışın "
        "parçasıdır, onlara normal şekilde atıfta bulunabilirsin."
    )
    return "\n".join(lines)



INVENTORY_INTENT_RE = re.compile(
    r"(envanter|stok\b|sayım|sayim|depoyu\s*(?:say|kontrol)|"
    r"kaç\s+(?:tane\s+)?(?:mermi|fişek|tavuk|keçi|konserve|litre|kutu)|"
    r"ne\s+kadar\s+(?:yiyecek|su|mermi|fişek|ilaç|yakıt|erzak|mahsul)|"
    r"kaynak(?:lar)?\s*(?:durum|listesi|sayım|kontrol))",
    re.IGNORECASE,
)



INVENTORY_REPORT_INSTRUCTION = (
    "ENVANTER SAYIMI TALEBİ: bu turda oyuncular grubun stoğunu saymak/kontrol "
    "etmek istiyor. Sahneyi normal kur, ama içinde sayımı KALEM KALEM ve "
    "SAYIYLA aktar (kategori kategori: yiyecek, su, tarım, hayvan, silah, "
    "mühimmat, tıbbi, yakıt, takas). Sayım sırasında hikaye gereği bir "
    "tutarsızlık çıkarabilirsin (eksik çıkan bir şey, bozulmuş erzak) — "
    "çıkarırsan `resources` alanını buna göre güncelle."
)



def inventory_note(world_state: dict) -> str:
    """Kimde ne var — her turda modele düz metin olarak verilir. JSON'un içine
    gömülü kalınca model bunu sık sık gözden kaçırıp olmayan eşya
    kullandırıyordu ("bıçağını çıkardı" — bıçağı yokken)."""
    lines = ["ENVANTER GERÇEĞİ (bu turda kimin üzerinde fiilen ne var):"]
    for name, info in (world_state.get("characters") or {}).items():
        if not info.get("alive", True):
            continue
        inv = info.get("inventory") or []
        lines.append(f"- {name}: {', '.join(inv) if inv else '(üzerinde hiçbir eşya yok)'}")
        lost = info.get("lost_items") or []
        if lost:
            lines.append(
                f"  · {name} ARTIK ŞUNLARA SAHİP DEĞİL (attı/verdi/kaybetti/"
                f"tüketti — hikayede fiilen geri almadıkça bir daha elinde "
                f"OLAMAZ): {', '.join(lost)}"
            )
    has_stock = any(
        isinstance(cat, dict) and cat
        for cat in (world_state.get("resources") or {}).values()
    )
    if not has_stock:
        lines.append(
            "ORTAK STOK: YOK. Grubun bir klanı, topluluğu ya da deposu henüz "
            "yok — elde SADECE yukarıdaki kişisel eşyalar var. Depodan, "
            "erzaktan, 'stoğumuzdan' söz ETME ve `resources` altına kendiliğinden "
            "kalem YAZMA. Stok ancak grup bir topluluk kurarsa/katılırsa ya da "
            "oyuncular açıkça sayım isterse doğar."
        )
    lines.append(
        "KURAL: bir karakter SADECE bu listedeki eşyaları, grubun `resources` "
        "stoğundan sahnede fiilen aldığı bir şeyi, ya da bulunduğu ortamda "
        "gerçekten var olan bir nesneyi kullanabilir. Listede olmayan bir eşyayı "
        "ASLA kullandırma — oyuncu mesajında 'bıçağımı çekiyorum' gibi yazsa "
        "bile bu sadece o oyuncunun iddiasıdır, gerçek değildir. Böyle bir "
        "durumda sahnede gerçekçi biçimde düzelt (eli boşa gider, cebinde "
        "olmadığını fark eder, eldeki başka bir şeyle idare etmek zorunda "
        "kalır) ve bunu kuru bir ret değil, küçük bir gerilim anına çevir."
    )
    lines.append(
        "SÜREKLİLİK: elden çıkmış bir eşya kendiliğinden geri GELMEZ. Bir "
        "karakter bir şeyi attıysa/verdiyse/kaybettiyse o şey artık bulunduğu "
        "yerdedir; ancak o yere geri dönüp FİİLEN alırlarsa envantere geri "
        "girer (o zaman `inventory_add` yaz). Aradan saatler geçmesi eşyayı "
        "cebe geri koymaz."
    )
    return "\n".join(lines)


# "envanter sayımı yapalım", "depoda ne kadar mermi var" gibi taleplerde
# arayüzdeki Grup Kaynakları paneli açılır ve anlatıcıdan kalem kalem döküm
# istenir. Panel bunun dışında kapalı durur — sürekli açık bir stok tablosu
# sahnenin içinde doğal durmuyordu.



def starting_items_note(world_state: dict) -> str:
    lines = []
    for name, info in (world_state.get("characters") or {}).items():
        inv = info.get("inventory") or []
        lines.append(f"- {name}: {', '.join(inv) if inv else '(eşya seçmedi)'}")
    return "\n".join(lines) if lines else "(karakter yok)"



def character_sheets_note(world_state: dict) -> str:
    """Kurulum ekranından gelen karakter künyeleri — sırlar dahil. Sadece
    modele gider, oyuncu arayüzüne asla."""
    lines = []
    for name, info in (world_state.get("characters") or {}).items():
        bits = []
        if info.get("age"):
            bits.append(f"yaş {info['age']}")
        if info.get("profession"):
            bits.append(f"meslek: {info['profession']}")
        if info.get("strength"):
            bits.append(f"güçlü yanı: {info['strength']}")
        if info.get("weakness"):
            bits.append(f"zayıf yanı: {info['weakness']}")
        inv = info.get("inventory") or []
        bits.append(f"başlangıç eşyası: {', '.join(inv) if inv else '(seçmedi)'}")
        lines.append(f"- {name} — " + "; ".join(bits))
        if info.get(SECRET_FIELD):
            lines.append(
                f"  · GİZLİ SIR (sadece sen bilirsin, asla açıklama): {info[SECRET_FIELD]}"
            )
    return "\n".join(lines) if lines else "(karakter yok)"





def roster_note(world_state: dict) -> str:
    """Her turda modele verilen sabit oyuncu kadrosu hatırlatması — model
    hikayenin ortasında isim uydurmasın/karıştırmasın diye."""
    characters = world_state.get("characters") or {}
    alive = _alive_players(world_state)
    dead = [n for n in characters if n not in alive]
    lines = [
        "OYUNCU KARAKTERLERİ (SABİT LİSTE — bunların dışında oyuncu karakteri YOKTUR): "
        + (", ".join(alive) if alive else "(yok)")
    ]
    if dead:
        lines.append(
            "ÖLMÜŞ oyuncu karakterleri (kalıcı olarak öldü, canlı gibi sahneye sokma): "
            + ", ".join(dead)
        )
    lines.append(
        "Bu isimleri harfi harfine, aynı yazımla kullan. Yeni bir oyuncu karakteri "
        "UYDURMA, mevcut birini başka isimle anma. Hikayedeki diğer herkes NPC'dir "
        "ve state-update'te `npcs` altına yazılır."
    )
    if any((characters.get(n) or {}).get(SECRET_FIELD) for n in alive):
        lines.append(
            "KÜNYE HATIRLATMASI: her karakterin `profession`/`age`/`strength`/"
            "`weakness` alanları BAĞLAYICIDIR — sahnede ve zar yorumunda "
            "kullan. `secret` alanı SADECE SANA aittir: asla açıklama, "
            "listeleme ya da başka bir karaktere söyletme; sadece gerilim "
            "kaynağı olarak, ima ve baskı yoluyla kullan."
        )
    return "\n".join(lines)



def presence_note(world_state: dict, returned=None, rejoined=None) -> str:
    """Her turda modele verilen sahne kadrosu — kimden hamle beklendiği,
    kimin sahnede olmadığı."""
    present = _present_players(world_state)
    absent = _absent_players(world_state)
    lines = [
        "SAHNE KADROSU — bu turda SAHNEDE olanlar: "
        + (", ".join(present) if present else "(kimse yok)")
    ]
    if absent:
        for name, presence in absent:
            bits = [PRESENCE_LABELS.get(presence["state"], presence["state"])]
            if presence.get("note"):
                bits.append(presence["note"])
            if presence.get("until"):
                bits.append("dönüş koşulu: " + describe_when(presence["until"]))
            lines.append(f"- SAHNE DIŞINDA · {name} — " + "; ".join(bits))
    for name, was in returned or []:
        lines.append(
            f"- GERİ DÖNDÜ · {name} ({PRESENCE_LABELS.get(was, was)} haliydi, koşulu "
            "doldu): bu turda sahneye gerçekten sok, dönüşünü göster."
        )
    for name in rejoined or []:
        lines.append(
            f"- GERİ DÖNDÜ · {name}: oyuncusu bu turda onun adına hamle yazdı, "
            "yani artık sahnede. Nasıl döndüğünü/uyandığını kısaca göster."
        )
    lines.append(
        "KURAL: sahne dışındaki karakter için replik, aksiyon ya da karar UYDURMA; "
        "ona zar yorumu yazma, ortak kararlara dahil etme. Sahnede olmadığı için "
        "ondan bu turda hiçbir şey duyulmaması NORMALDİR — yokluğunu açıklamak "
        "zorunda değilsin. Uzaktaki biri ancak sahnedekilerin gerçekten duyabileceği "
        "bir şekilde (telsiz, bağırış, geri dönüş) görünebilir."
    )
    lines.append(
        "KURAL: sahnede olan herkesin her turda konuşması ya da bir şey yapması da "
        "ŞART DEĞİL. Sadece o anki aksiyona gerçekten karışanları yaz; kalanları "
        "sırf sırayla söz vermek için sahneye sokma."
    )
    lines.append(
        "Bir karakter bu turda uyursa, nöbete/keşfe giderse, ayrılırsa, bayılırsa ya "
        'da esir düşerse state-update ile characters.<isim>.presence yaz — ör. '
        '{"state": "uyuyor", "note": "revirde", "until": {"day_gte": 99, "clock_gte": "06:00"}}. '
        "`until` koşulu dolduğunda sunucu onu otomatik sahneye döndürür; koşul "
        "yazmazsan sahneye dönmesi senin elinde kalır."
    )
    return "\n".join(lines)


# Her normal turda modele verilen "defter tutma" hatırlatması. Envanter ve
# grup stoğu buraya eklenmeden önce model bunları çoğu turda atlıyordu —
# hikayede ortaya çıkan bir bıçak arayüzdeki envanterde hiç görünmüyordu.



def vitals_note(world_state: dict) -> str:
    """Her turda modele verilen güncel gösterge tablosu — zar yorumunu
    bunlara göre kaydırması için."""
    lines = []
    for section in ("characters", "npcs"):
        for name, entry in (world_state.get(section) or {}).items():
            if not isinstance(entry, dict) or entry.get("alive") is False:
                continue
            vitals = entry.get("vitals")
            if not isinstance(vitals, dict):
                continue
            awake = vitals.get("awake_hours")
            lines.append(
                f"- {name}: yorgunluk {vitals.get('fatigue', 0)}, "
                f"açlık {vitals.get('hunger', 0)}, susuzluk {vitals.get('thirst', 0)}, "
                f"stres {vitals.get('stress', 0)}"
                + (f", {awake} saattir uyanık" if awake not in (None, "") else "")
                + f" → {vital_label(vitals)}"
            )
    if not lines:
        return ""
    return (
        "HAYATTA KALMA GÖSTERGELERİ (0 = iyi, 100 = dayanılmaz — sunucu akan "
        "zamana göre otomatik artırdı, GÜNCEL değerler bunlar):\n"
        + "\n".join(lines)
        + "\nBu değerleri bu turun anlatısında FİİLEN kullan: zar bandını "
        "yorgunluk/açlık/susuzluk seviyesine göre kaydır (40+ belirgin, 65+ "
        "bir kademe aşağı, 85+ neredeyse kesin bedelli), ve sonucu bir "
        "cümleyle değil yapılan işin SONUCUYLA göster. Bir karakter bu turda "
        "uyuduysa/yediyse/içtiyse `vitals` alanını state-update ile GÜNCELLE; "
        "aksi halde yazma, sunucu kendisi ilerletir."
    )



def wounds_note(world_state: dict) -> str:
    lines = []
    for section in ("characters", "npcs"):
        for name, entry in (world_state.get(section) or {}).items():
            if not isinstance(entry, dict) or entry.get("alive") is False:
                continue
            for wound in entry.get("wounds") or []:
                if not isinstance(wound, dict):
                    continue
                risk = wound.get("infection_risk") or 0
                flag = ("  ⚠️ ENFEKSİYON BELİRTİLERİ BAŞLADI" if risk >= 85
                        else "  ⚠️ enfeksiyon kapıda" if risk >= 60 else "")
                lines.append(
                    f"- {name}: {wound.get('desc')} ({wound.get('severity')}, "
                    f"enfeksiyon riski {risk}, "
                    + ("tedavi edildi" if wound.get("treated") else "TEDAVİ EDİLMEDİ")
                    + (f", not: {wound['notes']}" if wound.get("notes") else "")
                    + ")"
                    + flag
                )
    if not lines:
        return ""
    return (
        "AÇIK YARALAR (iyileşene kadar kayıtlı kalır — bu turda da FİİLEN "
        "hissedilsinler: ağrı, kanama, o uzvu kullanamama):\n"
        + "\n".join(lines)
        + "\nEnfeksiyon riski tedavi edilmedikçe zamanla kendiliğinden "
        "yükselir. 60'ı geçince belirtiler (ateş, titreme, kızarma) başlasın, "
        "85'i geçince bunu ölümcül bir `challenges` kaydına dönüştür. Tedavi "
        "edildiyse `wounds_update` ile `treated: true` yaz ve harcanan "
        "malzemeyi envanterden/`resources`'tan DÜŞ."
    )



UPKEEP_REMINDER = (
    "(3) ENVANTER KONTROLÜ (her tur, atlama): bu turun anlatısında bir "
    "karakterin elinde/üzerinde/cebinde bir eşya geçtiyse ve o eşya GÜNCEL "
    "DÜNYA DURUMU'nda o karakterin `inventory` listesinde YOKSA, aynı bloğa "
    "`inventory_add` ile ekle. Bir karakter bu turda bir eşyayı ATTIYSA, "
    "verdiyse, kaybettiyse, tükettiyse ya da kırdıysa AYNI TURDA "
    "`inventory_remove` ile çıkarmak ZORUNDASIN — yazmazsan eşya cebinde "
    "kalır ve hikaye tutarsızlaşır (atılan bir madalyon saatler sonra tekrar "
    "cepte çıkar). Anlatıda var olup envanterde görünmeyen ya da anlatıda "
    "elden çıkıp envanterde duran eşya kalmasın — oyuncular envanteri "
    "arayüzden canlı izliyor.\n"
    "(4) GRUP STOĞU: SADECE ortak bir depo/klan gerçekten varsa geçerlidir. "
    "Yoksa `resources`'a hiçbir şey yazma. Varsa ve bu turda bir şey "
    "harcandıysa/eklendiyse (mermi, yiyecek, su, ilaç, yakıt, hayvan, mahsul, "
    'takas malı...) güncelle — ör. {"Mühimmat": {"9mm mermi": "-3"}, '
    '"Yiyecek": {"Konserve": "+4"}}.\n'
    "(5) ZORLUKLAR: sahnedeki aktif `challenges` kayıtlarının `clock` ve "
    "`progress` alanlarını bu turda GÜNCELLE (oyuncu zarı ne kadar ilerletti, "
    "dünya zarı sorunu ne kadar büyüttü). Zorluk kapandıysa status'ü "
    "'çözüldü'/'başarısız' yap ve sonucunu gerçekten uygula. Sahnede aktif "
    "zorluk kalmadıysa yenisini aç.\n"
    "(6) BULMACALAR: oyuncular bu turda bir gizemle ilgili somut bir şey "
    "öğrendiyse `narrator.puzzles.<ad>` altında `progress` (0-100), "
    "`clues_found` ve `next_step` alanlarını güncelle — anlatıcı ekranı "
    "ilerlemeyi buradan izliyor.\n"
    "(7) ZAMAN VE HAVA (her tur, atlama): bu turdaki aksiyonların gerçekçi "
    "süresi kadar `clock`'u ilerlet, gerekirse `time_of_day`'i değiştir. "
    "Gece yarısı geçildiyse `day`'i 1 artır ve gün dönümü muhasebesini "
    "(tüketim, hayvan/tarım, iyileşme) `resources` ile birlikte işle. "
    "Hava değiştiyse `weather`/`temperature` alanlarını güncelle ve etkisini "
    "sahnede göster.\n"
    "(8) SAHNE KATILIMI: bir karakter bu turda uyuduysa, nöbete/keşfe gittiyse, "
    "gruptan ayrıldıysa, bayıldıysa ya da esir düştüyse "
    "`characters.<isim>.presence` yaz (`state` + gerekiyorsa `note` ve dönüş "
    "koşulu `until`); sahneye döndüyse `state`'i sahnede yap. SAHNE KADROSU "
    "bölümünde sahne dışında görünen karakterlere bu turda replik/aksiyon/karar "
    "YAZMA — susmaları normaldir, yokluklarını açıklama borcun yok.\n"
    "Ayrıca gerçekten değişen başka alanlar varsa (karakter durumu/ilişkisi, "
    "fraksiyon tavrı, gün, konum, yeni NPC, narrator.upcoming_events vb.) "
    "aynı bloğa ekle.\n"
    "SON OLARAK: yanıtını 'SAHNE YAPISI' bölümündeki **DURUM** + **SEÇENEKLER** "
    "bloğuyla bitir. Bu blok state-update'in DIŞINDA, oyuncuya görünen metnin "
    "son parçası olsun."
)
