# The Stoic Grove 🌲

Postează automat pe Instagram (**@thestoicgrove**) carusele de 10 slide-uri cu citate stoice și de filozofie, pe fundal de peisaje cu pădure generate procedural. Rulează gratuit pe GitHub Actions, de 3 ori pe zi.

- **Biblioteca de citate:** ~900 de citate cu sursă, de la 55 de autori (Marcus Aurelius, Seneca, Epictet, Thoreau, Emerson, Lao Tzu…). Ajung pentru ~38 de zile fără nicio repetare. După aceea se refolosesc cele mai vechi, cu o pauză de cel puțin 120 de zile pe citat.
- **Structura unui carusel:** copertă, 8 citate (pe o temă sau de la un autor), slide final cu îndemn la acțiune, plus descriere și 5 hashtag-uri.
- **Cost:** 0 lei.

## Pași de configurare (o singură dată)

### 1. Contul de Instagram
1. Creează contul (de exemplu @thestoicgrove). Poza de profil: `brand/profile_2.jpg`.
2. **Settings → Account type and tools → Switch to professional account → Creator.**
3. Bio:
   ```
   Ancient wisdom for a noisy world 🌲
   Stoic philosophy · daily quotes · quiet forests
   Save what speaks to you.
   ```

### 2. Tokenul pentru API (gratuit, ~10 minute)
1. Intră pe <https://developers.facebook.com/> și loghează-te cu contul de Facebook. Dacă ți se cere, înregistrează-te ca developer (se verifică telefonul).
2. **My Apps → Create App.** Nume: `Stoic Grove Poster`. Use case: **„Manage messaging & content on Instagram”**. La „business portfolio” alege să nu conectezi niciunul.
3. În aplicație mergi la **Use cases → Instagram → Customize → API setup with Instagram login**.
4. La **„Generate access tokens” → Add account**, loghează-te cu contul **@thestoicgrove**, acceptă permisiunile, apoi apasă **Generate token** și copiază tokenul.
   - Dacă primești o eroare de rol: **App roles → Roles → Add people → Instagram Tester → thestoicgrove**. Apoi acceptă invitația în Instagram (**Settings → Website permissions → Apps and websites → Tester invites**) și reîncearcă.
5. ⚠️ Tokenul e ca o parolă. Nu-l trimite nimănui și nu-l pune în chat sau în fișiere din repo.

### 3. GitHub
Repo-ul trebuie să fie **public**, pentru că Instagram descarcă imaginile de pe GitHub.
În repo: **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Valoare | Obligatoriu |
|---|---|---|
| `IG_ACCESS_TOKEN` | tokenul de la pasul 2 | da |
| `GH_PAT` | un token GitHub *fine-grained* pentru acest repo, cu permisiunea **Secrets: Read and write**. Îl folosește workflow-ul care reîmprospătează automat tokenul de Instagram (altfel expiră la 60 de zile). | recomandat |
| `PEXELS_API_KEY` | cheie gratuită de la <https://www.pexels.com/api/>, dacă vrei fotografii reale de pădure în loc de ilustrații | opțional |

### 4. Pornire
1. **Actions → Post carousel → Run workflow**, cu „dry_run” bifat. Construiește slide-urile fără să le posteze; le găsești la *Artifacts → slides*.
2. Rulează din nou fără „dry_run”. Asta e prima postare reală.
3. De aici înainte postează singur la 16:00, 20:30 și 02:00 (ora României, vara), adică dimineața, la prânz și seara în SUA. Orele se schimbă în `.github/workflows/post.yml`.

## Comenzi locale
```bash
pip install -r requirements.txt
python -m src.main preview --count 3   # 3 carusele în preview/ (cu _overview.jpg), fără să posteze
python -m src.main stats               # câte citate există pe fiecare temă și autor
IG_ACCESS_TOKEN=... python -m src.main check   # verifică tokenul și limita de postări
```

## Structura proiectului
- `quotes/authors/*.txt`: citatele triate, în formatul `text | autor | sursă | etichete`. Le poți edita direct.
- `quotes/themes/*.txt`: citate scrise manual. Numele fișierului devine eticheta.
- `themes.json`: titlurile caruselelor, descrierile, hashtag-urile și autorii.
- `config.json`: handle-ul, numărul de citate pe postare și perioada de pauză până un citat se poate repeta.
- `state/history.json`: ce s-a postat. Îl actualizează automat GitHub Actions.
- `tools/import_wikiquote.py`: importă candidați noi de pe Wikiquote în `quotes/_candidates/`. Trebuie triați înainte să fie folosiți.

## Sfaturi de creștere
- În primele 2-3 săptămâni răspunde la fiecare comentariu, pentru că algoritmul ține cont de asta.
- Pune caruselele cele mai bune (cele cu multe salvări) în **Highlights** sau fixează-le sus pe profil.
- Când ajungi pe la ~1.000 de urmăritori, adaugă un link în bio: o listă de cărți cu linkuri de afiliere (Amazon Associates) sau un PDF propriu (de exemplu „30-Day Stoic Journal” pe Gumroad).
