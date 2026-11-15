# Argentina: law history in git


The national law of Argentina as a git history: one file per article, one commit per law on the day it took effect, and the law or decree that made each change as the commit's author. `git blame` names the law behind every paragraph; `git log` lists every change to an article; picking a date gives the text in force that day.

Part of [lexifina/global-law](https://github.com/lexifina/global-law), one git history for every country's law: this is Argentina's national law, which global-law reads at `argentina/national/acts/`.

**What is in it now:** the Constitution and 138 national codes and laws, among them the Código Civil y Comercial, the Código Penal and the Ley de Contrato de Trabajo, with 775 versions in force from 1933 to 2026; 7 of the laws have since been repealed, and their history ends with a version that has no provisions. 6 more versions, due to take effect later, are on the `futuro` branch. [`data/versions.json`](data/versions.json) lists every act with the day each version took effect; [`data/laws.csv`](data/laws.csv) lists every norm the record names, with its dates.

Each act is a folder named after it (`ley-20744/`, `codigo-civil-y-comercial/`), with one file per article: `ley-20744/art-245.md` is art. 245 of the Ley de Contrato de Trabajo (Ley 20.744, texto ordenado 1976). The four acts taken from Argentina.gob.ar are one file each, `texto.md`. Each folder's `README.md` lists its provisions and when each changed.

The text is in Spanish, as InfoLEG (or Argentina.gob.ar) publishes it, with InfoLEG's notes left out. InfoLEG keeps only two texts of each norm, the text as enacted and today's consolidated text, so the versions in between are rebuilt by applying each amending norm's own published instructions in order of entry into force.

## Questions as git commands

| Question | Command |
| --- | --- |
| Every change to art. 245 of the Ley de Contrato de Trabajo | `git log -p --word-diff -- ley-20744/art-245.md` |
| Which law wrote each paragraph of art. 245? | `git blame ley-20744/art-245.md` |
| Every version of the Ley de Contrato de Trabajo, with the day each took effect | `git log --format="%h %(trailers:key=In-force,valueonly,separator=) %an" -- ley-20744 ":^ley-20744/README.md"` |
| Art. 245 as in force on 1 January 2023 | `python tools/en_vigor_el.py 2023-01-01 ley-20744 245` |

**Outside git**, we also host this record publicly, for free:

- **[Ask Claude about Argentine law](https://global-law.lexifina.com/v1/try_claude?country=argentina)**: opens Claude with a first question ready.
- **[Ask ChatGPT](https://global-law.lexifina.com/v1/try_chatgpt?country=argentina)**: the same question in ChatGPT.
- **[Search Argentine law on our site](https://lexifina.com/law?country=argentina&q=vacaciones+anuales)**: a search for "vacaciones anuales", with each provision's text and its versions, no account needed.
- **[Developer REST API](https://global-law.lexifina.com/v1/search_law?query=vacaciones+anuales&jurisdiction=argentina)**: the same search as JSON, with no key. See the [documentation here](https://lexifina.com/api/global-law).

Both assistants read the record through the free Global law connector (MCP, `https://global-law.lexifina.com/mcp`); the first time, the chat gives you the link that adds it. Ask in Spanish or in English.

**Host it yourself easily.** All it takes is git and Python, and the tools run on your machine:

```sh
git clone --depth 1 https://github.com/lexifina/global-law && cd global-law
python3 tools/countries.py add argentina/national/acts
python3 tools/law.py show 2026-01-01 argentina/national/acts/ley-20744/art-245.md
```

Opened in Claude Code, Cursor, VS Code or Codex, the clone also starts a local MCP server with the same tools ([MCP.md](https://github.com/lexifina/global-law/blob/main/MCP.md)).

## Dates

Each commit is dated at noon, America/Argentina/Buenos_Aires, on the day the change took effect, and carries it in its `In-force:` trailer, beside `Enacted:` and `Published:` (the Boletín Oficial day):

- a norm's own vigencia clause decides ("a partir del día siguiente al de su publicación"); without one, Código Civil y Comercial art. 5 ("Las leyes rigen después del octavo día de su publicación oficial"), counted under art. 6, puts it on the ninth day after publication; before 1 August 2015 the same rule was Código Civil art. 2, as replaced by Ley 16.504;
- staged starts, extensions and terms that run out (the Código Procesal Penal Federal district by district, Ley 25.561's emergency) are commits that change no words, on their own day;
- git cannot store dates before 1970, so the 6 earlier commits are dated from 1970-01-01, one second apart, with the real day in `In-force:`. Ask for a date with `tools/en_vigor_el.py`, not `git log --before`.

Each change is credited to the law or decree that made it, with an address that cannot exist (`Ley 27.802 <ley-27802@infoleg.invalid>`; decrees of necessity and urgency as `DNU 70/2023`), so `git blame` and `git log --author` name laws. A first version taken from a texto ordenado, a consolidated text or an archived capture is credited to its publisher, InfoLEG (11 acts) or Argentina.gob.ar (4), as the "oldest version available"; the committer is Lexifina.

## How it is checked

- Today's rebuilt text of every act InfoLEG consolidates is compared, article by article, with InfoLEG's consolidated text of the retrieval day: 0 differences in wording, apart from the few listed in `REPRODUCE.md` (such as "integral" in art. 86 of the Código Penal, which Decreto 14/2021 vetoed and InfoLEG keeps with a note). The acts that start from a 2013 capture were also checked against later captures (2014 to 2025).
- `tools/check_repo.py` reads every version back from git on the day it took effect and on the day before; both must match the corpus, whose sha256 is in `data/corpus.sha256`: 781 versions of 139 acts, 0 mismatches ([`REPRODUCE.md`](REPRODUCE.md)).
- The same corpus gives the same commit hashes (`tools/build.py`); `REPRODUCE.md` records that no second build has been compared yet.
- History is append-only (`tools/append.py`): no merge commits on `main`, no commit dates that go backwards, nothing dated in the future, and every commit's trailers parse.

## What it does not show

- **All national law.** These are 139 acts, not the whole statute book; regulatory decrees and resolutions that only complement an act, and case law, are not here.
- **Changes before an act's first version**, which are inside that first commit: for example the Constitution before 1994, the Ley de Contrato de Trabajo before 1976 and the Código Penal before 1985. InfoLEG serves no older text of the Códigos Procesales Civil y Comercial and Penal, Ley 24.522 or the Código Aduanero, so they start from 2013 captures of InfoLEG's pages, dated by the capture day; Leyes 13.064, 17.671, 22.431 and 27.351 are today's text only.
- **Changes that leave the words alone**: suspensions, emergency measures, court rulings (such as those on the labour chapter of DNU 70/2023) and treaties given constitutional hierarchy have no commit.
- **Headings, notes and vetoed words.** Headings of books, titles and chapters are not kept, InfoLEG's notes are removed, and words vetoed on promulgation are left out.
- **Provincial and city law**, which is in its own repositories (such as [argentina-buenos-aires-law](https://github.com/lexifina/argentina-buenos-aires-law)), read by global-law beside this one under `argentina/`.

## Sources

| Source | Kind | Past versions | Notes |
| --- | --- | --- | --- |
| [InfoLEG](https://www.infoleg.gob.ar) (Ministerio de Justicia de la Nación) | Official database of national legislation | no: the text as enacted and today's consolidated text | Every act's texts and the amending norms' own texts; its notes name the norm behind each change |
| [Base de datos InfoLEG](https://datos.jus.gob.ar/dataset/base-de-datos-legislativos-infoleg) (datos.jus.gob.ar) | Open dataset, CC BY 4.0 | n/a | Each norm's type, number, dates and title |
| [Internet Archive Wayback Machine](https://web.archive.org/) | Captures of InfoLEG's pages | yes, dated captures from 2013 | The first version of four acts, and the checks against later captures |
| [Argentina.gob.ar, Leyes Argentinas](https://www.argentina.gob.ar/normativa) (Ministerio de Justicia) | Official legislation | no, today's text | Leyes 13.064, 17.671, 22.431 and 27.351 |

## Licence

See [`LICENSE`](LICENSE). The legal texts are official texts of the Argentine Nation, reproduced with the attribution "Fuente: InfoLEG - Información Legislativa, Ministerio de Justicia de la Nación (www.infoleg.gob.ar)"; InfoLEG's pages publish no licence and the texts' copyright status is not confirmed, while the InfoLEG dataset (norm types, numbers, dates and titles) is CC BY 4.0. Lexifina's own contributions (the arrangement, commit messages, tables and tools) are CC0 1.0.

No AI model wrote, translated or corrected legal text, and none runs at build time; the scripts were written by Claude Code running Claude Opus 5.5 (see [`REPRODUCE.md`](REPRODUCE.md)).

## En español

Historia del derecho nacional argentino en git: un archivo por artículo y un commit por norma, fechado el día de su entrada en vigencia y firmado por la norma que hizo el cambio. Contiene la Constitución Nacional y 138 códigos y leyes nacionales, con 775 versiones; las que aún no rigen están en la rama `futuro`. Texto vigente en una fecha: `python tools/en_vigor_el.py 2023-01-01 ley-20744 245`. Fuente: InfoLEG - Información Legislativa, Ministerio de Justicia de la Nación (www.infoleg.gob.ar).

## More

From [lexifina/global-law](https://github.com/lexifina/global-law):

- [FEATURES.md](https://github.com/lexifina/global-law/blob/main/FEATURES.md): every feature, and what every corpus must support (`git blame`, `law.py`, the MCP tools)
- [FAQ.md](https://github.com/lexifina/global-law/blob/main/FAQ.md): questions and answers · [CONTRIBUTING.md](https://github.com/lexifina/global-law/blob/main/CONTRIBUTING.md): proposing changes · [MCP.md](https://github.com/lexifina/global-law/blob/main/MCP.md): the MCP server · [REPRODUCE.md](https://github.com/lexifina/global-law/blob/main/REPRODUCE.md): how it was built · [CHANGELOG.md](https://github.com/lexifina/global-law/blob/main/CHANGELOG.md)
- [FRESHNESS.md](https://github.com/lexifina/global-law/blob/main/FRESHNESS.md): how current each corpus is · [Monitoring](https://github.com/lexifina/global-law/tree/main/monitoring): whether updates are running · [WATCHING.md](https://github.com/lexifina/global-law/blob/main/WATCHING.md): how each official source is watched for changes
- [performance/](https://github.com/lexifina/global-law/tree/main/performance): how fast the tools are, measured
- [visualisations/](https://github.com/lexifina/global-law/tree/main/visualisations): charts and bridges across the world's law
- [Vulnerabilities](https://github.com/lexifina/global-law/tree/main/vulnerabilities): mistakes in legislation as published
