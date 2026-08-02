"""Bir turun `extra_system` metinleri.

`turn_service` yalnız akışı yönetsin diye modele giden uzun bloklar buraya
alındı. Metinler eski `server.py`'deki halleriyle BİREBİR aynıdır — tek
karakteri bile değişmemelidir; parçalar `prompt_builder`'dan gelir.
Hepsi world_state SÖZLÜĞÜ ile çalışır (WorldState.to_dict() çıktısı).
"""

import json

from app.services import prompt_builder


def notes_block(ws: dict, log: list, scene_note: str = None) -> str:
    """Her turda modele giden "defter": kadro → (sahne kadrosu) → envanter →
    yaralar → göstergeler → görünür zaman çizelgesi. Bloklar arası ayraç eski
    kodda olduğu gibi tek boş satırdır."""
    parts = [prompt_builder.roster_note(ws)]
    if scene_note is not None:
        parts.append(scene_note)
    parts += [
        prompt_builder.inventory_note(ws),
        prompt_builder.wounds_note(ws),
        prompt_builder.vitals_note(ws),
        prompt_builder.visible_timeline_note(log),
    ]
    return "\n\n".join(parts)


def multi_extra_system(ws, log, combined, in_chargen, world_entry,
                       inventory_block, scene_note) -> str:
    """Aynı mesajda birden fazla karakterin hamlesi ('İsim: aksiyon')."""
    if in_chargen:
        return (
            "ÇOKLU KARAKTER TURU — KARAKTER OLUŞTURMA AŞAMASI, zar mekaniği YOK.\n"
            "Aşağıdaki her satır farklı bir oyuncunun AYNI ANDA gönderdiği karakter "
            "oluşturma cevabıdır. Her biri için (gerçekten karakterini kuruyorsa) "
            "state-update bloğuna characters.<isim> altına background, traits VE "
            "inventory_add (mesleğine uyan 2-3 mütevazı başlangıç eşyası; kurulum "
            "ekranında seçtikleri eşya zaten envanterlerinde, tekrar ekleme) "
            "eklemeyi UNUTMA — hepsi TEK bir state-update bloğunda birleşsin.\n\n"
            + combined
            + "\n\n"
            + notes_block(ws, log)
            + "\n\nGÜNCEL DÜNYA DURUMU (JSON):\n"
            + json.dumps(ws, ensure_ascii=False)
        )
    return (
        "ÇOKLU KARAKTER TURU — SCENARIO'daki 'ÇOKLU KARAKTER TURU' bölümüne "
        "göre davran: aşağıdaki her satır farklı bir karakterin AYNI ANDA "
        "aldığı farklı bir aksiyon, her biri KENDİ zarına göre ayrı ayrı "
        "sonuçlanır ama sahneyi birleşik/akıcı anlat.\n"
        + prompt_builder.world_dice_note(world_entry)
        + inventory_block
        + "\n\nHATIRLATMA: yanıtının sonuna TEK bir state-update bloğu ekle. "
        "(1) tension ve (2) narrator.plot_summary (2-4 cümlelik güncel "
        "özet) her turda zorunlu.\n"
        + prompt_builder.UPKEEP_REMINDER
        + "\n\n"
        + combined
        + "\n\n"
        + notes_block(ws, log, scene_note)
        + "\n\nGÜNCEL DÜNYA DURUMU (JSON):\n"
        + json.dumps(ws, ensure_ascii=False)
    )


def chargen_extra_system(ws, log, player, is_group) -> str:
    """Karakter oluşturma sürerken: zar yok, künye toplanıyor."""
    if is_group:
        chargen_head = (
            "KARAKTER OLUŞTURMA AŞAMASI — zar mekaniği uygulanmaz.\n"
            "Bu mesaj [GRUP - ORTAK KARAR] etiketiyle geliyor: tek bir "
            "karakterin değil, grubun ortak sözü/aksiyonu. Karakter "
            "oluşturma henüz bitmemiş olabilir; grubu birlikte ele al, "
            "hâlâ karakterini kurmamış olan varsa ona kısaca hatırlat.\n\n"
        )
    else:
        chargen_head = (
            "KARAKTER OLUŞTURMA AŞAMASI — bu turda zar mekaniği uygulanmaz.\n"
            f"Bu mesajı yazan: {player}. Eğer bu mesajda {player} karakterini "
            "kuruyorsa (bir seçenek seçtiyse ya da kendi tarifini yazdıysa), "
            "yanıtının sonuna MUTLAKA ```state-update``` bloğu ekleyip "
            f"characters.{player} altına background, traits VE inventory_add "
            "(mesleğine/geçmişine uyan 2-3 mütevazı başlangıç eşyası; kurulum "
            "ekranında seçtiği eşya zaten envanterinde, onu tekrar ekleme) "
            "alanlarını yaz — bunu unutma, atlarsan karakter bilgisi kalıcı "
            "olarak kaybolur.\n\n"
        )
    return (
        chargen_head
        + notes_block(ws, log)
        + "\n\nGÜNCEL DÜNYA DURUMU (JSON, sadece senin referansın, oyunculara okuma):\n"
        + json.dumps(ws, ensure_ascii=False)
    )


def turn_extra_system(ws, log, is_group, roll, band, world_entry,
                      inventory_block, scene_note) -> str:
    """Olağan tur: oyuncu zarı + dünya zarı + tur sonu defter tutma."""
    group_note = (
        "Bu mesaj [GRUP - ORTAK KARAR] etiketiyle geliyor — SCENARIO'daki "
        "'ORTAK KARAR MESAJLARI' bölümüne göre davran, tek bir karaktere "
        "değil TÜM gruba ait bir karar/aksiyon olarak ele al.\n\n"
        if is_group else ""
    )
    return (
        f"ZAR (oyuncunun hamlesi): {roll} ({band})\n"
        + prompt_builder.world_dice_note(world_entry)
        + inventory_block
        + "\n\n"
        + group_note
        + "HATIRLATMA (teknik, MUTLAKA uygula): yanıtının SONUNA bir "
        "```state-update``` bloğu ekle ve içine EN AZINDAN şunları yaz — "
        "bu iki alan her turda zorunlu, başka hiçbir şey değişmese bile "
        'atlama: (1) bu sahnenin "tension" seviyesi (\"düşük\"/\"orta\"/'
        '\"yüksek\"); (2) `narrator.plot_summary` — hikayenin şu anki '
        "durumunun 2-4 cümlelik güncel özeti (bu SADECE anlatıcı ekranında "
        "görünür, oyunculara asla gösterilmez).\n"
        + prompt_builder.UPKEEP_REMINDER
        + "\n\n"
        + notes_block(ws, log, scene_note)
        + "\n\nGÜNCEL DÜNYA DURUMU (JSON, sadece senin referansın, oyunculara okuma):\n"
        + json.dumps(ws, ensure_ascii=False)
    )


def takeover_extra_system(ws, log, dead_key, new_key) -> str:
    """Ölen karakterin oyuncusu hikayedeki bir NPC'yi devralıyor."""
    return (
        "KARAKTER DEVRALMA TURU — zar mekaniği YOK.\n"
        f"{dead_key} kalıcı olarak öldü ve ölü kalacak; onun oyuncusu artık "
        f"{new_key} karakterini oynuyor. {new_key} bu andan itibaren bir NPC "
        "DEĞİL, bir OYUNCU KARAKTERİDİR — state-update'te `characters` altında "
        "takip et ve doğrudan ona hitap et.\n"
        f"Kısa (1-2 paragraf) bir geçiş sahnesi yaz: {new_key} sahnenin/grubun "
        f"merkezine nasıl geçiyor, {dead_key}'in ölümü gruba nasıl yansıyor. "
        f"Sonra {new_key}'e ne yapacağını sor.\n"
        "Yanıtının sonuna TEK bir state-update bloğu ekle; içinde en azından "
        "tension ve narrator.plot_summary olsun.\n\n"
        + prompt_builder.roster_note(ws)
        + "\n\n"
        + prompt_builder.inventory_note(ws)
        + "\n\n"
        + prompt_builder.visible_timeline_note(log)
        + "\n\nGÜNCEL DÜNYA DURUMU (JSON):\n"
        + json.dumps(ws, ensure_ascii=False)
    )
