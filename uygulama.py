import psycopg2
import os
from nicegui import ui
import hashlib
from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from nicegui import app

app.add_static_files('/static', 'static')

# --- 1. Veritabanı Fonksiyonları ---

DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://canatalay:canatalay.374@localhost:5432/kutuphane")
# SQLAlchemy ile bağlantı kurarken bu adresi kullanın

def get_connection():
    return psycopg2.connect(
        dbname="kutuphane",
        user="canatalay",
        password="canatalay.374",
        host="localhost",   # <--- Docker Compose'da servis adı db ama normal bilgisayarda localhost!
        port="5432"
    )

def veritabani_olustur():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS kullanicilar (
        id SERIAL PRIMARY KEY,
        isim TEXT,
        email TEXT UNIQUE,
        sifre TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS kitaplar (
        id SERIAL PRIMARY KEY,
        ad TEXT,
        yazar TEXT,
        yayinevi TEXT,
        basim_yili INTEGER
    )''')
    conn.commit()
    conn.close()

def hash_sifre(sifre: str) -> str:
    return hashlib.sha256(sifre.encode('utf-8')).hexdigest()

def kullanici_ekle(isim, email, sifre):
    try:
        sifre_hashli = hash_sifre(sifre)
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO kullanicilar (isim, email, sifre) VALUES (%s, %s, %s)', (isim, email, sifre_hashli))
        conn.commit()
        conn.close()
        return (True, 'Kayıt başarılı!')
    except psycopg2.IntegrityError:
        return (False, 'Bu e-posta zaten kullanılıyor!')
    except Exception as e:
        return (False, f'Hata: {e}')

def kullanici_dogrula(email, sifre):
    sifre_hashli = hash_sifre(sifre)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM kullanicilar WHERE email = %s AND sifre = %s', (email, sifre_hashli))
    kullanici = cursor.fetchone()
    conn.close()
    return kullanici is not None

def kitap_ekle(ad, yazar, yayinevi, basim_yili):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO kitaplar (ad, yazar, yayinevi, basim_yili) VALUES (%s, %s, %s, %s)',
                   (ad, yazar, yayinevi, basim_yili))
    conn.commit()
    conn.close()

def kitap_guncelle(kitap_id, ad, yazar, yayinevi, basim_yili):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''UPDATE kitaplar SET ad = %s, yazar = %s, yayinevi = %s, basim_yili = %s WHERE id = %s''',
                   (ad, yazar, yayinevi, basim_yili, kitap_id))
    conn.commit()
    conn.close()

def kitaplari_getir():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, ad, yazar, yayinevi, basim_yili FROM kitaplar ORDER BY id DESC')
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    kitaplar = [dict(zip(columns, row)) for row in rows]
    conn.close()
    return kitaplar

def kitap_sil(kitap_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM kitaplar WHERE id = %s', (kitap_id,))
    conn.commit()
    conn.close()

def admin_kullanicisi_olustur():
    isim = "Admin"
    email = "canatalay374@gmail.com"
    sifre = "canatalay.374" # Güvenli bir şifre kullanın, gerçek uygulamada hash'leyin!
    sifre_hashli = hash_sifre(sifre)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM kullanicilar WHERE email = %s', (email,))
    if cursor.fetchone() is None:
        try:
            cursor.execute('INSERT INTO kullanicilar (isim, email, sifre) VALUES (%s, %s, %s)', (isim, email, sifre_hashli))
            conn.commit()
            print("Admin kullanıcısı oluşturuldu.")
        except psycopg2.IntegrityError:
            print("Admin kullanıcısı zaten mevcut.")
    conn.close()

def tum_kullanicilari_getir():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, isim, email, sifre FROM kullanicilar ORDER BY id ASC')  # sifre eklendi
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    kullanicilar = [dict(zip(columns, row)) for row in rows]
    conn.close()
    return kullanicilar

def kullanici_sil_db(kullanici_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM kullanicilar WHERE id = %s', (kullanici_id,))
    conn.commit()
    conn.close()

def eski_sifreleri_hashle():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, sifre FROM kullanicilar')
    users = cursor.fetchall()
    for user_id, sifre in users:
        # Eğer şifre zaten hash'li ise (64 karakter ve sadece hex karakterler içeriyorsa) atla
        if len(sifre) == 64 and all(c in '0123456789abcdef' for c in sifre):
            continue
        yeni_hash = hash_sifre(sifre)
        cursor.execute('UPDATE kullanicilar SET sifre = %s WHERE id = %s', (yeni_hash, user_id))
    conn.commit()
    conn.close()
    print('Tüm eski şifreler hash\'lendi.')

# --- 2. NiceGUI Arayüzü ---

ui.add_head_html("""
<style>
body {
    background: red !important;
}
</style>
""")

@ui.page('/')
def giris_sayfasi():
    ui.add_head_html("""
<style>
body {
    background: url('/static/kutuphaneresim.jpg') no-repeat center center fixed;
    background-size: cover;
}
</style>
""")
    with ui.card().classes('absolute-center w-96'):
        ui.label("Kütüphane Giriş").classes('text-2xl font-bold self-center')
        email = ui.input("E-posta Adresi").props('outlined dense')
        sifre = ui.input("Şifre", password=True, password_toggle_button=True).props('outlined dense')
        
        def giris_yap_handler():
            if not email.value or not sifre.value: 
                ui.notify("Lütfen tüm alanları doldurun.", type="warning")
                return
            
            girilen_email = email.value.strip().lower()
            girilen_sifre = sifre.value.strip()

            if kullanici_dogrula(girilen_email, girilen_sifre):
                ui.notify("Giriş başarılı! 🎉", color='positive')
                # Admin kontrolü
                if girilen_email == "canatalay374@gmail.com" and girilen_sifre == "canatalay.374":
                    ui.navigate.to('/admin') # Admin ise admin paneline
                else:
                    ui.navigate.to('/kitaplar') # Normal kullanıcı ise kitaplar sayfasına
            else: 
                ui.notify("E-posta veya şifre hatalı.", type="negative")

        ui.button("Giriş Yap", on_click=giris_yap_handler).classes('mt-4 w-full')
        ui.button("Yeni Hesap Oluştur", on_click=lambda: ui.navigate.to('/kayit')).classes('mt-2 w-full').props('flat')

@ui.page('/kayit')
def kayit_sayfasi():
    ui.add_head_html("""
    <style>
    body {
        background: url('/static/kutuphaneresim.jpg') no-repeat center center fixed;
        background-size: cover;
    }
    </style>
    """)
    with ui.card().classes('absolute-center w-96'):
        ui.label('Yeni Kullanıcı Kaydı').classes('text-2xl font-bold self-center')
        isim = ui.input('İsim Soyisim').props('outlined dense')
        email = ui.input('E-posta Adresi').props('outlined dense')
        sifre = ui.input('Şifre', password=True, password_toggle_button=True).props('outlined dense')
        def kayit_ol_handler():
            if not isim.value or not email.value or not sifre.value: ui.notify('Lütfen tüm alanları doldurun!', type='warning'); return
            basarili, mesaj = kullanici_ekle(isim.value.strip(), email.value.strip().lower(), sifre.value.strip())
            if basarili: ui.notify(mesaj, color='positive'); ui.navigate.to('/')
            else: ui.notify(mesaj, type='negative')
        ui.button("Kaydol", on_click=kayit_ol_handler).classes("mt-4 w-full")
        ui.button("Giriş Ekranına Dön", on_click=lambda: ui.navigate.to('/')).classes('mt-2 w-full').props('flat')

@ui.page('/kitaplar')
def kitap_sayfasi():
    ui.label('📚 Kitap Yönetim Sistemi').classes('text-3xl font-bold self-center')

    with ui.row().classes('w-full items-start no-wrap'):
        # Sol: Kitap ekleme formu
        with ui.card().classes('w-96'):
            ad = ui.input('Kitap Adı')
            yazar = ui.input('Yazar')
            yayinevi = ui.input('Yayınevi')
            basim_yili = ui.number('Basım Yılı', format='%.0f')
            def kitap_ekle_handler():
                if not ad.value or not yazar.value:
                    ui.notify('Kitap adı ve yazar zorunludur.', type='warning')
                    return
                kitap_ekle(ad.value, yazar.value, yayinevi.value, basim_yili.value)
                ui.notify('Kitap başarıyla eklendi!', color='positive')
                ad.value, yazar.value, yayinevi.value, basim_yili.value = '', '', '', None
                build_kitap_listesi.refresh()
            ui.button('Kitabı Kaydet', on_click=kitap_ekle_handler)

        # Sağ: Arama ve kitap listesi
        with ui.column().classes('w-full'):
            arama_metni = ui.input('Kitap Ara...', on_change=lambda: build_kitap_listesi.refresh()).props('outlined dense clearable icon=search').classes('w-full max-w-lg mt-4')

            @ui.refreshable
            def build_kitap_listesi():
                tum_kitaplar = kitaplari_getir()
                # Arama metni varsa filtreleme yap
                if arama_metni.value:
                    filtreli_kitaplar = [
                        kitap for kitap in tum_kitaplar 
                        if arama_metni.value.lower() in kitap['ad'].lower() or
                           arama_metni.value.lower() in kitap['yazar'].lower() or
                           arama_metni.value.lower() in kitap['yayinevi'].lower() or
                           arama_metni.value.lower() in str(kitap['basim_yili']).lower()
                    ]
                else:
                    filtreli_kitaplar = tum_kitaplar

                if not filtreli_kitaplar:
                    ui.label("Aradığınız kriterlere uygun kitap bulunmamaktadır." if arama_metni.value else "Henüz kayıtlı kitap bulunmamaktadır.").classes('text-center text-gray-500 mt-4')
                    return

                for kitap in filtreli_kitaplar:
                    with ui.row().classes('w-full items-center p-2 border-b'):
                        with ui.column().classes('flex-grow'):
                            ui.label(kitap['ad']).classes('font-bold')
                            ui.label(f"Yazar: {kitap['yazar']} | Yıl: {kitap['basim_yili']}").classes('text-sm text-gray-600')

                        async def duzenle_handler(_, k=kitap):
                            with ui.dialog() as duzenle_dialog, ui.card():
                                yeni_ad = ui.input('Kitap Adı', value=k['ad'])
                                yeni_yazar = ui.input('Yazar', value=k['yazar'])
                                yeni_yayinevi = ui.input('Yayınevi', value=k['yayinevi'])
                                yeni_yil = ui.number('Basım Yılı', value=k['basim_yili'], format='%.0f')
                                with ui.row().classes('justify-end'):
                                    ui.button('İptal', on_click=duzenle_dialog.close)
                                    def kaydet_handler():
                                        kitap_guncelle(k['id'], yeni_ad.value, yeni_yazar.value, yeni_yayinevi.value, yeni_yil.value)
                                        ui.notify('Kitap güncellendi!', color='positive')
                                        duzenle_dialog.close()
                                        build_kitap_listesi.refresh()
                                    ui.button('Kaydet', on_click=kaydet_handler, color='primary')
                            await duzenle_dialog

                        async def kitap_sil_onayla(k_id):
                            with ui.dialog() as sil_dialog, ui.card():
                                ui.label('Bu kitabı silmek istediğinize emin misiniz?')
                                with ui.row():
                                    ui.button('İptal', on_click=sil_dialog.close)
                                    def sil_ve_yenile():
                                        kitap_sil(k_id)
                                        sil_dialog.close()
                                        build_kitap_listesi.refresh()
                                    ui.button('Sil', on_click=sil_ve_yenile, color='negative')
                            await sil_dialog

                        ui.button('Düzenle', on_click=duzenle_handler, color='blue').props('dense')
                        ui.button('Sil', on_click=lambda _, k_id=kitap['id']: kitap_sil_onayla(k_id), color='red').props('dense')

            build_kitap_listesi()

    ui.button('Çıkış Yap', on_click=lambda: ui.navigate.to('/')).props('color=negative outline').classes('absolute-top-right mt-4 mr-4')

@ui.page('/admin')
def admin_paneli():
    ui.label('⚙️ Admin Paneli').classes('text-3xl font-bold self-center q-mt-md')

    async def kullanici_sil_onay(kullanici_id: int, kullanici_isim: str):
        with ui.dialog() as onay_dialogu, ui.card():
            ui.label('Onay Gerekiyor').classes('text-xl')
            ui.label(f"'{kullanici_isim}' adlı kullanıcıyı silmek istediğinizden emin misiniz?")
            ui.label("Bu işlem geri alınamaz!").classes('text-red-600 font-bold')
            with ui.row().classes('w-full justify-end q-mt-md'):
                ui.button('İptal', on_click=onay_dialogu.close, color='primary')
                ui.button('Sil', on_click=lambda: onay_dialogu.submit('evet'), color='negative')
        
        sonuc = await onay_dialogu
        if sonuc == 'evet':
            kullanici_email_cek_conn = get_connection()
            kullanici_email_cek_cursor = kullanici_email_cek_conn.cursor()
            kullanici_email_cek_cursor.execute('SELECT email FROM kullanicilar WHERE id = %s', (kullanici_id,))
            result = kullanici_email_cek_cursor.fetchone()
            if result is not None:
                silinecek_email = result[0]
                kullanici_email_cek_conn.close()

                if silinecek_email == "canatalay374@gmail.com":
                    ui.notify("Admin hesabını silemezsiniz!", type="negative")
                else:
                    kullanici_sil_db(kullanici_id)
                    ui.notify(f"'{kullanici_isim}' adlı kullanıcı başarıyla silindi.", color='positive')
                    kullanici_listesi_kapsayici.clear()
                    with kullanici_listesi_kapsayici:
                        build_kullanici_listesi()
            else:
                ui.notify("Kullanıcı bulunamadı.", type="warning")
                kullanici_listesi_kapsayici.clear()
                with kullanici_listesi_kapsayici:
                    build_kullanici_listesi()
            
    def build_kullanici_listesi():
        kullanicilar = tum_kullanicilari_getir()
        if not kullanicilar:
            ui.label("Henüz kayıtlı kullanıcı bulunmamaktadır.").classes('text-center text-gray-500 mt-4')
            return
            
        for kullanici in kullanicilar:
            with ui.row().classes('w-full items-center p-2 border-b'):
                with ui.column().classes('flex-grow'):
                    ui.label(f"ID: {kullanici['id']}").classes('text-sm text-gray-500')
                    ui.label(kullanici['isim']).classes('font-bold')
                    ui.label(kullanici['email']).classes('text-sm text-blue-600')
                    ui.label(f"Şifre: {kullanici['sifre']}").classes('text-sm text-red-600')  # Şifreyi göster
                
                if kullanici['email'] == "canatalay374@gmail.com":
                    ui.label("Admin Hesabı").classes('text-info text-sm')
                else:
                    ui.button('Sil', on_click=lambda _, k_id=kullanici['id'], k_isim=kullanici['isim']: kullanici_sil_onay(k_id, k_isim), color='red').props('dense')

    ui.label('Sistemdeki Kullanıcılar').classes('text-xl font-semibold q-mt-lg')
    ui.separator().classes('my-2')
    
    kullanici_listesi_kapsayici = ui.column().classes('w-2/3 max-w-lg mx-auto q-mt-md')

    # --- Kullanıcı Ekleme Dialogu ve Butonu ---
    async def kullanici_ekle_dialog():
        with ui.dialog() as ekle_dialog, ui.card():
            ui.label('Yeni Kullanıcı Ekle').classes('text-lg font-bold')
            yeni_isim = ui.input('İsim Soyisim').props('outlined dense')
            yeni_email = ui.input('E-posta Adresi').props('outlined dense')
            yeni_sifre = ui.input('Şifre', password=True, password_toggle_button=True).props('outlined dense')
            with ui.row().classes('justify-end'):
                ui.button('İptal', on_click=ekle_dialog.close)
                def ekle_handler():
                    if not yeni_isim.value or not yeni_email.value or not yeni_sifre.value:
                        ui.notify('Tüm alanları doldurun!', type='warning')
                        return
                    basarili, mesaj = kullanici_ekle(yeni_isim.value.strip(), yeni_email.value.strip().lower(), yeni_sifre.value.strip())
                    if basarili:
                        ui.notify(mesaj, color='positive')
                        ekle_dialog.close()
                        kullanici_listesi_kapsayici.clear()
                        with kullanici_listesi_kapsayici:
                            build_kullanici_listesi()
                    else:
                        ui.notify(mesaj, type='negative')
                ui.button('Ekle', on_click=ekle_handler, color='primary')
        await ekle_dialog

    ui.button('Kullanıcı Ekle', on_click=kullanici_ekle_dialog, color='primary').classes('mb-4')

    with kullanici_listesi_kapsayici:
        build_kullanici_listesi()

    ui.button('Kitap Yönetimine Dön', on_click=lambda: ui.navigate.to('/kitaplar')).props('color=primary outline').classes('mt-4')
    ui.button('Çıkış Yap', on_click=lambda: ui.navigate.to('/')).props('color=negative outline').classes('ml-2 mt-4')


# --- 3. Uygulamayı Başlatma ---
if __name__ in {"__main__", "__mp_main__"}:
    veritabani_olustur()
    admin_kullanicisi_olustur()
    eski_sifreleri_hashle()  # <-- Bir defa çalıştır, sonra silebilirsin
    ui.run(title="Kütüphane Sistemi")

