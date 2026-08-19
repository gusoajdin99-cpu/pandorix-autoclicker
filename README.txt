========================================
   PANDORIX AUTOCLICKER - BEZ TERMINALA
========================================

Ovo uputstvo pravi tvoj .exe fajl BEZ ijedne komande na tvom racunaru.
Sve se radi preko browsera (klikom misa), a sam .exe se pravi na
GitHub-ovom serveru (pravi Windows racunar u oblaku) i ti ga onda samo
preuzmes gotovog.

Treba ti samo besplatan GitHub nalog. Traje oko 5 minuta.


KORAK 1 - Napravi besplatan GitHub nalog (ako ga nemas)
-----------------------------------------------------------
Idi na: https://github.com/signup
Popuni email, sifru, korisnicko ime - besplatno je.


KORAK 2 - Napravi novi repozitorij (folder na GitHub-u)
------------------------------------------------------------
1. Klikni na zeleno dugme "New" (ili idi na https://github.com/new)
2. Za "Repository name" upisi npr: pandorix-autoclicker
3. Ostavi ga na "Public" (privatni radi na istom nacinu, ali javni
   ima besplatnu Actions minutazu bez ogranicenja)
4. Klikni "Create repository"


KORAK 3 - Otpremi fajlove (drag & drop, bez komandi)
----------------------------------------------------------
1. Na stranici novog repozitorija, klikni link "uploading an existing file"
   (ili idi u "Add file" -> "Upload files")
2. Otvori ovaj folder (raspakovan iz zipa koji sam ti poslao) na svom
   racunaru i PREVUCI SVE FAJLOVE I FOLDERE unutra u browser
   (pandorix_autoclicker.py, requirements.txt, logo.png, logo.ico,
   build_exe.bat, README.txt, i folder ".github")

   VAZNO: folder ".github" mora ostati folder (ne raspakivati sadrzaj
   van njega) - prevucanjem citavog raspakovanog foldera trebalo bi
   automatski da ponese i njega.

3. Dolje klikni zeleno dugme "Commit changes"


KORAK 4 - Pokreni automatsko pravljenje .exe
--------------------------------------------------
1. Na vrhu stranice repozitorija klikni tab "Actions"
2. Sa lijeve strane klikni "Build Pandorix EXE"
3. Klikni dugme "Run workflow" (plavo/sivo dugme desno), pa opet
   "Run workflow" u meniju koji se otvori
4. Sacekaj 1-3 minuta - stranicu mozes osvjezavati (F5). Kad pored
   pokrenutog workflow-a vidis zelenu kvacicu, gotovo je.


KORAK 5 - Preuzmi gotov .exe
-----------------------------
1. Klikni na zavrseni (zeleni) workflow run
2. Na dnu stranice, u sekciji "Artifacts", klikni na
   "Pandorix-AutoClicker-EXE" - preuzece se ZIP
3. Otpakuj taj zip - unutra je "Pandorix AutoClicker.exe", spreman
   za koriscenje, sa tvojim logom kao ikonom.

Taj .exe mozes slobodno prekopirati na Desktop, USB, gdje god zelis -
ne treba mu ni Python ni internet da bi radio, potpuno je samostalan.


NAPOMENA
---------
- Windows Defender / SmartScreen ce vjerovatno prvi put upozoriti da je
  .exe "od nepoznatog izdavaca" jer nije digitalno potpisan (to kosta
  novac i nije vezano za nas kod) - klikni "More info" -> "Run anyway".
- Ako i dalje zelis da probas lokalni nacin (build_exe.bat), staro
  uputstvo je i dalje ispravno - ali ovaj GitHub nacin ne trazi
  nikakvu komandu na tvom racunaru.


ALTERNATIVA AKO NE ZELIS NI GITHUB
-------------------------------------
Ako ti ni ovo ne odgovara, mogu da ti napravim jednostavniji .py fajl
koji pokrecemo direktno duplim klikom (bez .exe), ali tada ti je
ipak potreban instaliran Python na racunaru (samo instalacija,
bez ikakvih komandi nakon toga - dupli klik na .py i radi).
Javi mi ako zelis tu varijantu.
