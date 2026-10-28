# Argentina: law history in git

The national law of Argentina as a git history: one file per provision, one commit per law on the day it took effect, and the law that made each change as the commit's author. `git blame` names the law behind every paragraph; `git log` lists every change to an article; checking out a date gives the text in force that day.

It follows the shared design of [lexifina/global-law](https://github.com/lexifina/global-law), which places it at `ar/`.

**What is in it now**

| Folder | Act | Versions | History |
| --- | --- | ---: | --- |
| `constitucion/` | Constitución de la Nación Argentina | 1 | The text in force since the 1994 reform (24 August 1994); its words have not changed since |
| `codigo-civil-y-comercial/` | Código Civil y Comercial de la Nación (Ley 26.994) | 12 | As enacted, in force 1 August 2015, to today: 12 amending laws and decrees, the last Ley 27.799 (2 January 2026) |
| `ley-25326/` | Ley 25.326 de Protección de los Datos Personales | 2 | As promulgated (in force 11 November 2000) and art. 47 added by Ley 26.343 (2008) |
| `codigo-penal/` | Código Penal (Ley 11.179, texto ordenado 1984) | 72 | From the texto ordenado of Decreto 3992/1984 (published 16 January 1985) to today: 78 amending laws and decrees, the last Ley 27.786 (11 March 2025) |
| `ley-20744/` | Ley de Contrato de Trabajo (Ley 20.744, texto ordenado 1976) | 39 | From the texto ordenado of Decreto 390/1976 (published 21 May 1976) to today: 42 amending laws and decrees, the last Ley 27.802 de Modernización Laboral (6 March 2026) |
| `codigo-procesal-penal-federal/` | Código Procesal Penal Federal (Ley 27.063, texto ordenado 2019) | 18 | From its first application (Salta and Jujuy, 10 June 2019) through each step of its staged entry into force and Leyes 27.784 and 27.785 (March 2025); three steps still to come (Paraná, Buenos Aires, Córdoba) are on the branch `futuro` |

The per-act `README.md` in each folder lists every provision, how often it changed and when.

**How the history was made.** InfoLEG, the official database of national legislation, keeps only two texts of each norm: the text as enacted (`norma.htm`) and today's consolidated text (`texact.htm`), whose notes name the norm behind each changed article. It keeps no versions in between. Every version after the first is therefore rebuilt by applying, in order of entry into force, each amending norm's own instructions as InfoLEG publishes them ("Sustitúyese el artículo 1198 del Código Civil y Comercial de la Nación por el siguiente: …"). The rebuilt text of today is then compared with InfoLEG's consolidated text, article by article: on 28 October 2026 every act matched word for word, with one deliberate exception in the Código Penal (see "How it is checked").

## A lawyer's questions as git commands

| Question | Command |
| --- | --- |
| What did art. 1198 of the Código Civil y Comercial say on 1 January 2023? | `python tools/en_vigor_el.py 2023-01-01 codigo-civil-y-comercial 1198` |
| The same, with raw git (bash) | `git show $(git rev-list -1 --before="2023-01-01T23:59:59Z" main -- codigo-civil-y-comercial/art-1198.md):codigo-civil-y-comercial/art-1198.md` |
| The same, in PowerShell | `$r = git rev-list -1 --before="2023-01-01T23:59:59Z" main -- codigo-civil-y-comercial/art-1198.md; git show "$($r):codigo-civil-y-comercial/art-1198.md"` |
| Which law wrote each paragraph of art. 1221? | `git blame codigo-civil-y-comercial/art-1221.md` |
| Every change to art. 1198, word by word | `git log -p --word-diff codigo-civil-y-comercial/art-1198.md` |
| Every law in the record, in order | `git log --reverse --format="%ad %an" --date=short main` |
| Everything one law changed | `git show law/decreto-70-2023` (tags `law/<key>` mark each law's commit) |
| The whole act on a date | `python tools/en_vigor_el.py 2020-12-31 codigo-civil-y-comercial` |
| The act on the day a version took effect | `git show codigo-civil-y-comercial/2020-07-01` (tags `<act>/<in-force day>`) |
| Laws passed but not yet in force | `git log main..futuro` (the Código Procesal Penal Federal's next steps: Paraná 2026-11-30, Buenos Aires 2027-02-15, Córdoba 2027-03-08) |

After a rebuild, refresh tags with `git fetch --force --tags`: a plain fetch keeps stale tags.

## Dates

- Each commit is dated at **noon, America/Argentina/Buenos_Aires, on the day the change took effect** (the in-force date). Sanción and publication dates are trailers (`Enacted:`, `Published:`, the Boletín Oficial day), and the in-force day is in `In-force:`, which the tools read.
- **A norm's own vigencia clause decides** ("a partir del día de su publicación", "a partir del día siguiente al de su publicación"). InfoLEG repeats it as "Vigencia: …" in the note on each article it changed; the clause in each amending norm's text was read by hand and is listed in `REPRODUCE.md`.
- **Default rule.** Without such a clause a norm is in force after the eighth day following its publication: Código Civil y Comercial art. 5 ("Las leyes rigen después del octavo día de su publicación oficial, o desde el día que ellas determinen"), counted under art. 6 (the day of publication is excluded), so from the ninth day after publication. Before 1 August 2015 the same rule was Código Civil (Ley 340) art. 2, as replaced by Ley 16.504 ("serán obligatorias después de los ocho días siguientes al de su publicación oficial").
- **Decreto 70/2023** (a DNU, published on 21 December 2023) has no vigencia clause, so the default rule dates its changes to the Código Civil y Comercial **30 December 2023**. The Government and the press announced 29 December (eight days counted from publication). We keep the count the rule gives and note the difference.
- **The Código Civil y Comercial** was approved by Ley 26.994 (Boletín Oficial, 8 October 2014). Its art. 7 set 1 January 2016; Ley 27.077 brought that forward to **1 August 2015**, the date of its first commit.
- **The Constitution's** 1994 reform "entra en vigencia al día siguiente de su publicación" (Disposición transitoria decimosexta), and its oath was taken on 24 August 1994: its single commit is dated 1994-08-24. The text is InfoLEG's official text ordered by Ley 24.430 (Boletín Oficial, 10 January 1995).
- `--before="YYYY-MM-DD"` alone uses your clock's time of day, so a law that took effect that day may be missed before noon. Use `T23:59:59Z` as above, or the tool.

## How it is checked

- **Against the official text.** `tools/parse.py` rebuilds today's text of each act by the replay and compares it, article by article, with InfoLEG's `texact.htm` of the retrieval day. On 2026-10-28: Código Civil y Comercial 0 differences in wording (one article, art. 75, differed only in typography and uses InfoLEG's consolidated typography from the version in which it last changed); Ley 25.326 0 differences. The Constitution has no consolidated text on InfoLEG because it has not been amended since 1994. Ley de Contrato de Trabajo: 0 differences in wording. Código Penal: 0 differences in wording, except that art. 86 inc. 2 leaves out the word "integral", which Decreto 14/2021 vetoed and InfoLEG keeps in its text with a note.
- **The Código Procesal Penal Federal** takes effect district by district. Its words are rebuilt like the other acts (0 differences from InfoLEG's consolidated text), and every step of its entry into force that InfoLEG records is a commit with no words changed, credited to the resolution that set it and to the provisions it brings into force: the Comisión Bicameral's resolutions that applied single articles nationwide (2019 to 2021) and the Ministerio de Justicia's resolutions for each federal district (2024 to 2026). The first commit, 10 June 2019, is its start in Salta and Jujuy; InfoLEG does not record that date, which comes from Resolución PGN 127/2019 of the Procuración General de la Nación. Which district applies the code on a given day is in the commit notes, not in the files.
- **The Ley de Contrato de Trabajo** was rebuilt the same way from its 1976 texto ordenado: 52 unamended articles take the consolidated wording from the first version (transcription and layout differences only), 10 articles changed by partial instructions take the consolidated wording from their last named norm, and the changes of Ley 24.522 (not on InfoLEG: art. 251; arts. 264 to 266 repealed) come from InfoLEG's notes.
- **The Código Penal needed more judgement**, all of it listed in `REPRODUCE.md`: 39 articles that no norm changed differ between InfoLEG's transcription of the 1984 texto ordenado and its consolidated text only by transcription (for example "programado" and "propagado" in art. 114), and use the consolidated wording from the first version; 32 articles changed by partial instructions (an inciso or a paragraph) take the consolidated wording from the last norm InfoLEG names for them, so their earlier versions are the replay's own placing of each change; three fines-update laws (Leyes 23.479, 23.974, 24.286) changed amounts by reference, without rewriting the articles, and are commits with no words changed; Leyes 24.453 and 24.454 (1995) are not on InfoLEG, so their changes (arts. 74, 118 repealed; art. 181) come from InfoLEG's notes and consolidated text.
- Two articles of the Código Civil y Comercial differ in InfoLEG's text as enacted only by transcription errors ("testa-mento" in art. 2277, "Iegitimarios" in art. 2446). Neither was ever amended; the first version uses the consolidated wording.
- Every version of every act is read back from git on the day it took effect and on the day before (`tools/check_repo.py`); both must match `corpus.json`. Results are in `REPRODUCE.md`.
- Health checks: no merge commits on `main`, commit dates never go backwards, nothing dated in the future, and every commit's trailers parse with `git interpret-trailers --parse`.
- The repository is rebuilt from the same data a second time and must give identical hashes.

## What "author" means

The author of a commit is the law or decree that made the change, with an e-mail address that cannot exist (`ley-27551@infoleg.invalid`), so `git blame` and `git log --author` name laws. The committer is always Lexifina.

- **Credits come from the amending norm itself.** A changed article is credited to the norm whose instruction changed it, and InfoLEG's note on the article in the consolidated text names the same norm for its last change.
- **Decrees of necessity and urgency (DNU)** are commits of kind "decree", cited as "DNU 70/2023". Under Ley 26.122 a DNU stays in force unless both chambers of Congress reject it, so none is marked temporary; InfoLEG's consolidated text of the retrieval day carries the changes of every DNU here.
- **Unexplained changes** would be committed by the publisher, InfoLEG, and labelled "unexplained". There are none.
- Blame credits whole lines (one paragraph per line). In an article written by several laws, use `git log -p --word-diff` to see exactly which words each law changed.

## What it does not show

- **The Código Penal before 1985.** The code of 1921 and its amendments to 1984 (including de facto laws and their repeal) are in the first commit, the texto ordenado of 1984, not one by one. Headings of the code's books, titles and chapters, and the 23 instructions that only renamed them, are not kept.
- **The Código Procesal Civil y Comercial de la Nación.** InfoLEG serves neither its text as enacted (1967) nor its texto ordenado of 1981, only today's text, so its history cannot be rebuilt from this source and it is not included.
- **The Ley de Contrato de Trabajo before 1976**, the unnumbered articles that Ley 24.576 added in 1995 (a Chapter VIII on training, repealed by Ley 27.802 in 2026), and court rulings on the labour chapter of DNU 70/2023, which are not modelled: the record follows InfoLEG's consolidated text.
- **The Constitution before 1994.** InfoLEG publishes only the current text (1853, with the reforms of 1860, 1866, 1898, 1957 and 1994). Those earlier texts are named in the first commit, not shown. Ley 24.430 art. 2 states that the official text includes the second paragraph of art. 77, which the August 1994 printing had omitted; the 1994 printing is not in our sources, so that omission is not shown.
- **Treaties with constitutional hierarchy.** Leyes 27.044 (2014) and 27.700 (2022) gave further treaties the hierarchy of art. 75 inc. 22 without changing its words, so they have no commit.
- **Ley 27.551's abrogation.** Decreto 70/2023 art. 249 abrogated Ley 27.551, but InfoLEG's consolidated text keeps the Code articles Ley 27.551 wrote and Decreto 70/2023 did not replace (arts. 1203, 1209, 1222, 1351). We follow InfoLEG.
- **Suspensions and emergency rules that leave the words alone**, such as the 2020 rent emergency decrees (DNU 320/2020 and its extensions) that suspended evictions and froze rents. They change no word of the Code and have no commit.
- **Applicability.** Ley 27.551 applies to contracts concluded from its entry into force (art. 23), and Ley 27.363 also to situations pending at its entry into force (art. 3). These are recorded as `Applies:` trailers and in `corpus.json`, but the text on a date does not depend on them.
- **The vetoed text of Ley 25.326.** Decreto 995/2000 vetoed art. 29 points 2 and 3 and art. 47 of the bill. That text never took effect and is not shown.
- **Headings, notes and regulations.** The headings of books, titles, chapters and sections are not kept; InfoLEG's notes ("Artículo sustituido por …", "Nota Infoleg: …") are removed from the text; regulatory decrees and resolutions that only complement an act are not in it.

## How it is built

`tools/fetch.py` downloads every source page once through curl (one request per second, cached by the sha256 of the URL), `tools/parse.py` turns the cache into `corpus.json` (the replay and the check against the consolidated text), and the shared builder `tools/build.py` writes the history with `git fast-import`. The same corpus always gives the same hashes. `REPRODUCE.md` records every command, tool version, data hash and decision, and the result of a hash-for-hash rebuild.

No AI model wrote or changed legal text. Claude Opus 5.5 wrote the scripts and chose the sources; see `REPRODUCE.md`.

## Sources

| Source | Kind | Past versions | Names the amending act | Bulk | Notes |
| --- | --- | --- | --- | --- | --- |
| [InfoLEG](https://servicios.infoleg.gob.ar/infolegInternet/), Ministerio de Justicia de la Nación | Official legislation | no: the text as enacted and today's consolidated text | yes, a note per article in the consolidated text | per norm | Used: `norma.htm` (texto original), `texact.htm` (texto actualizado), `verNorma.do` (record), `verVinculos.do` (norms that modify or complement a norm) |
| [Base de datos InfoLEG](https://datos.jus.gob.ar/dataset/base-de-datos-legislativos-infoleg) (datos.jus.gob.ar) | Dataset, CC BY 4.0 | n/a | links between norms | CSV (updated to 30 September 2026) | Used for each norm's type, number, class (DNU), sanción and Boletín Oficial dates and titles |
| [argentina.gob.ar/normativa](https://www.argentina.gob.ar/normativa) | Official legislation | no | yes | no | The same texts as InfoLEG; not used |
| [Boletín Oficial](https://www.boletinoficial.gob.ar) | Official gazette | n/a | n/a | no | Not read: the amending norms' texts are on InfoLEG |

Research guides that cover every country: [GlobaLex](https://www.nyulawglobal.org/globalex/) and the [Law Library of Congress Guide to Law Online](https://www.loc.gov/research-centers/law-library-of-congress/researcher-resources/guide-to-law-online/).

## Licence

The legal texts are official texts of the Argentine Nation, as published by the Ministerio de Justicia de la Nación in InfoLEG. Fuente: InfoLEG - Información Legislativa, Ministerio de Justicia de la Nación (www.infoleg.gob.ar). The InfoLEG dataset on datos.jus.gob.ar is published under Creative Commons Attribution 4.0; InfoLEG's own pages carry "Copyright 2005" and no licence. The arrangement, tables, commit messages and tools are by Lexifina, under the terms in `LICENSE`.

This repository is not legal advice and not an official publication.

## En español

Historia del derecho nacional argentino en git: un archivo por artículo y un commit por norma, fechado el día de su entrada en vigencia y firmado por la norma que hizo el cambio (`git blame` nombra la ley o el decreto de cada párrafo). Contiene la Constitución Nacional (texto vigente desde la reforma de 1994), el Código Civil y Comercial de la Nación desde su entrada en vigencia el 1 de agosto de 2015 hasta la Ley 27.799 (2026), la Ley 25.326 de Protección de los Datos Personales desde 2000, el Código Penal desde el texto ordenado de 1984 (Decreto 3992/1984) hasta la Ley 27.786 (2025), la Ley de Contrato de Trabajo desde el texto ordenado de 1976 (Decreto 390/1976) hasta la Ley 27.802 (2026), y el Código Procesal Penal Federal desde su primera aplicación (Salta y Jujuy, 10 de junio de 2019), con cada paso de su entrada en vigencia progresiva; los pasos futuros están en la rama `futuro`.

- Texto vigente en una fecha: `python tools/en_vigor_el.py 2023-01-01 codigo-civil-y-comercial 1198`
- Cómo se hizo: InfoLEG no guarda versiones intermedias, solo el texto original y el texto actualizado. Cada versión se reconstruye aplicando, por orden de entrada en vigencia, el texto de cada norma modificatoria, y el resultado de hoy se compara artículo por artículo con el texto actualizado de InfoLEG (coincidencia total el 28 de octubre de 2026).
- Fechas: la cláusula de vigencia de cada norma; si no tiene, el art. 5 del Código Civil y Comercial (antes, el art. 2 del Código Civil): rige después del octavo día de su publicación en el Boletín Oficial.
- Fuente: InfoLEG - Información Legislativa, Ministerio de Justicia de la Nación (www.infoleg.gob.ar). Ningún modelo de IA escribió texto legal.
