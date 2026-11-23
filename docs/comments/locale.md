# Comments in `locale`

Written by `chatddx-dev index` from the comments in `[parts.locale]`'s code in `settings.toml`, sorted by file and then by name whatever its case:

````
## `<file>:<the name it is in or right above>`

```
<the comment, as written>
```
````

- A comment in or above no name is under its file alone, and comments on lines one after another are one.
- A stamp pending is a git conflict, from `<<<<<<< signed` to `=======` as last stamped and on to the `>>>>>>>` closing it as written now, till it is stamped.

## `frontend/src/lib/locale.ts:LANGUAGE_PARAMS`

```
// Policy: a parameter named so holds a language's tag, and one named languages tags
// separated by ", ", each said by its name, as the server says them.
```

## `frontend/src/lib/locale.ts:LISTED_PARAMS`

```
// Policy: a parameter named so holds names separated by ", ", said as a list, as the server says it.
```

## `frontend/src/lib/locale.ts:th`

```
// Policy: a message holding markup is markup, as a translation is trusted as the server's are;
// what is put into it is escaped, as a {% trans %} block's variables are.
```

## `frontend/src/lib/locale.ts:worded`

```
// Accommodating for JavaScript, which writes some numbers other than Python does: what the
// page's catalog doesn't hold is said as the server wrote it, but for the languages it
// names and the lists it holds, which the server writes by their tags and joined by ", ".
```

## `src/chatddx/locale/locale.py:_extracted`

```
# Accommodating for Babel, whose type for an extraction method's results
# leaves out the name of the function called, which it reads.
```

## `src/chatddx/locale/locale.py:_LANGUAGE_PARAMS`

```
# Policy: a parameter named so holds a language's tag, and one named languages tags
# separated by ", ", each said by its name where the message is said.
```

## `src/chatddx/locale/locale.py:_LISTED_PARAMS`

```
# Policy: a parameter named so holds names separated by ", ", said as a list.
```

## `src/chatddx/locale/locale.py:_locale`

```
# Policy: a catalog is said as last stamped, so that a translation pending is said as it
# was, or in English while it's new, till it is stamped.
```

```
# Policy: what isn't reviewed is a stamp pending, so a fuzzy flag is said as any other.
```

## `src/chatddx/locale/locale.py:_LOCALIZING`

```
# Accommodating for Jinja, whose macros imported without context see nothing of the page
# rendering them: a page is said in the locale set around its rendering.
```

## `src/chatddx/locale/locale.py:_refusals`

```
# Policy: a refusal whose wording isn't written where it is raised is marked where it is
# written, with pgettext_noop and the context refusal.
```

## `src/chatddx/locale/locale.py:_restamped`

```
# Policy: a catalog is written in step with the code on both sides of its stamps, each
# matched to the code by its messages alone, never by a guess at a changed message's
# closest translation, which is left untranslated to be translated anew, and in the
# order of the messages, so that what is left to stamp is the translations alone.
```

## `src/chatddx/locale/locale.py:_shared`

```
# Policy: the catalog put in an island's page holds only what the islands say, and what the
# API may answer them with: the whoopses, and what is said below the portal.
```

## `src/chatddx/locale/locale.py:_SOURCES`

```
# Policy: what a whoops tells the person is said in their locale wherever it is raised;
# what it has them pass on to developers and ops isn't.
```

## `src/chatddx/locale/locale.py:_updated`

```
# Accommodating for Babel, which matches a new message to an untranslated plural one as
# if it were translated: what holds no translation comes anew from the code.
```

## `src/chatddx/locale/locale.py:CHOSEN`

```
# Policy: the cookie that keeps the locale a person chose over their browser's.
```
