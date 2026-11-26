# Catalog

How people name, own, share and follow what the store holds: threads of components and their edits, families and where
their vignettes are, and the entries said of a thread, a family, a run or a score. Components are the store's and runs
and scores the ledger's; the catalog keeps what changes around them. `chatddx.catalog` is plain Python over a `Reader`
(`src/chatddx/catalog/read.py:Reader`): it reads and checks, and writes nothing. The store gives it its rows
(`src/chatddx/store/catalog.py:Rows`) and writes them (`src/chatddx/store/catalog.py:Catalog`). The surface is stamped
in `docs/surfaces/catalog.md`.

## Principles

- **Append-only, derived when read.** Threads, edits, families, bindings, entries, labels and languages are inserted and
  never changed. A thread's head is its latest edit (`src/chatddx/catalog/threads.py:head`), and a version what an edit
  holds, numbered by the first edit to hold it, so that one brought back is that version again
  (`src/chatddx/catalog/threads.py:versions`); a family's current binding its latest, and what is said of a subject is
  `About.of` its entries, latest winning, tags and collaborators each by their own latest
  (`src/chatddx/catalog/model.py:About.of`). Deleting is an entry too, and so is restoring.
- **Checked before every write.** Each of `Catalog`'s writes runs the catalog's check in its transaction:
  `check_create`, `check_edit`, `check_note`, `check_language` and `check_adoptable`, and `plan_repair` for a repair.
  The database's tier 2 repeats the rules concurrent writers could break, as each `Duplication:` comment says, and
  `docs/migrations.md` ("catalog") lists.
- **An edit names the head it was made on.** An edit is refused with `MovedOn` once its thread has moved on from that
  head (`src/chatddx/catalog/threads.py:check_edit`), and the store locks the thread for the check and the insert.
  Keeping what a thread's head holds already writes nothing (`src/chatddx/catalog/threads.py:holds`).
- **Forks are compared with their base.** A fork is a thread `forked_from` an edit of its origin, its base that edit or
  the origin's edit it last followed (`based_on`). What its head varies from its base is a `Divergence`, by recipe part
  when both are compiled and by field otherwise; once its origin has moved on, the origin's head with those changes on
  top is its `proposal`. `behind` lists what a thread's head refers to that live threads have moved on from, facts only
  where they change what it sends, and its cases whose family has a newer binding.
- **Kinds say what has a thread and a language.** `THREAD_KINDS` have threads; `LANGUAGE_KINDS` hold a language of their
  own, kept on the digest rather than the thread, so that a text is in one language wherever it is held. A compiled
  skeleton's language is the one its recipe's texts agree on, or the one it was translated into; a case's is its
  family's `language` entry; an expectation, a trial and a judge follow what they name
  (`src/chatddx/catalog/language.py:languages_of`).
- **One live expectation per person, case and schema.** An edit, an owner entry or a restoring entry that would give a
  person a second one is refused (`src/chatddx/catalog/threads.py:_check_expectation`). `expecting` lists the heads of a
  case's expectations under a schema, and `picked` gives the one digest some threads hold, refusing when they hold
  different ones.
- **A family follows its vignette.** A case finds its family by a binding to its vignette, an earlier one included
  (`src/chatddx/catalog/families.py:family_of`). A case that gives a family's current vignette a new name or new content
  can't make a family of its own: the family is repaired instead (`check_adoptable`). `survey` compares a source's
  listing with the bindings, and `plan_repair` moves a family to a new id or new content: its cases and appendices
  rebuilt, its appendix threads moved, and on a rename its expectation threads too.
- **Titles are built, never stored.** A thread's title is its name, else for a fork its origin's title and what it
  varies, else a description of what its head holds (`src/chatddx/catalog/titles.py:title`); a digest's prefers the
  names of the threads that hold it, current ones first (`title_of`).
- **Who sees what isn't the catalog's.** It says who owns and collaborates on a subject; `chatddx.identity`'s `owns` and
  `sees` decide over that, and the bench filters by them.
- **Errors.** `LookupError` for what isn't there, `ValueError` for what a rule refuses, and `MovedOn`, a `ValueError`,
  for a head moved on from. The bench and the edges say them in their own terms.

## Sensitive

The catalog holds no vignette text. A binding holds where a vignette is and its fingerprint, which is plain, so a short
typed text's can be guessed (`docs/parts/clearance.md`, "Typed vignettes"). A case's title is its family's name, else
its vignette's `SOURCE/ID`, with its appendices' snippets; appendices aren't sensitive.

## Flows

The flows of `docs/parts/api.md` ("Flows"), as the catalog sees them, read back in `python` in the dev shell after they
ran. The blocks run in one session, each on what the one before it set.

1. **Signing in, and asking who that is**, writes nothing to the catalog and reads nothing from it: a person is in the
   catalog as the `by` of every row, and the person of owner and collaborator entries. What alice sees is the subjects
   those entries make her the owner or a collaborator of, which loading the sample shared with her:

   ```python
   import psycopg
   from chatddx import settings
   from chatddx.catalog import Subject, language, read, threads, titles
   from chatddx.identity import owns, sees
   from chatddx.store import People, Rows

   conn = psycopg.connect(settings.database(), autocommit=True)
   rows, alice = Rows(conn), People(conn).find("alice")
   said = read.abouts(rows, rows.involving(alice.id))
   seen = {s: a for s, a in said.items() if sees(alice.id, a)}
   [s for s, a in seen.items() if owns(alice.id, a)]
   ```

2. **Configuring components**: the chunk's language is kept on its digest (`Catalog.language`), and `Catalog.create`
   starts a `chunk.instructions` thread with its first edit and her owner and name entries. The fork is a `skeleton`
   thread `forked_from` the archive's head of `plan`, its edit holding the skeleton and its compilation. Looking at the
   variation writes nothing:

   ```python
   [fork] = threads.find(rows, "skeleton", "plan-terse", owner=alice.id)
   head = threads.head(rows, fork)
   titles.title(rows, threads.origin(rows, fork)), threads.divergence(rows, fork).varies
   language.language_of(rows, head.digest)
   ```

3. **Running and scoring**: taking forks the archive's expectation thread, which `expecting` found, into one of hers.
   The run is a subject of its own, with her owner entry, its name, and the edit it varied (`Entry.varied`), the parts
   replaced over it (`Entry.replaced`) and the run it was started with (`Entry.started_with`) when it has them; each
   score is a subject with her owner entry. The rest of a run and its scores is in the ledger, which the catalog doesn't
   read:

   ```python
   [taken] = [e for e, a in threads.heads(rows, "expectation") if owns(alice.id, a)]
   titles.title(rows, taken.thread), threads.origin(rows, taken.thread)
   [run] = [s.run for s, a in seen.items() if s.run and a.varied == head.id]
   read.about(rows, Subject(run=run))
   ```

4. **Reading runs** takes from the catalog what is said of each run and what it ran: the configuration and the edit it
   varied, the parts replaced, its name, and the language of its skeleton:

   ```python
   about = read.about(rows, Subject(run=run))
   ran = rows.edit(about.varied)
   ran.thread == fork, about.name, about.replaced, language.language_of(rows, ran.digest)
   ```
