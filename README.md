# Notifications-admin

Notifications admin application.


## Upstream

This repo is a clone / modifed version of:
https://github.com/alphagov/notifications-admin


## Features of this application

 - Register and manage users
 - Create and manage services
 - Send batch emails and SMS by uploading a CSV
 - Show history of notifications


## Functional constraints

- We currently do not support sending of letters
- We currently do not receive a response if text messages were delivered or not


## First-time setup

[Brew is a package manager](https://brew.sh/) for OSX. The following command installs brew:
```shell
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Languages needed
- Python 3.10
- [Node](https://nodejs.org/) 10.15.3 or greater
- [npm](https://www.npmjs.com/) 6.4.1 or greater

```shell
    brew install node
```

[NPM](npmjs.org) is Node's package management tool. `n` is a tool for managing
different versions of Node. The following installs `n` and uses the long term support (LTS)
version of Node.

```shell
    npm install -g n
    n lts
    npm rebuild node-sass
```


### Local installation instruction

On OS X:

1. Install PyEnv with Homebrew. This will preserve your sanity.

`brew install pyenv`

2. Install Python 3.10.8 or whatever is the latest

`pyenv install 3.10.8`

3. If you expect no conflicts, set `3.10.8` as you default

`pyenv global 3.10.8`

4. Ensure that version `3.10.8` is now the default by running

`python --version`

If it did not, add to your shell rc file. ex: `.bashrc` or `.zshrc`
```
eval "$(pyenv init --path)"
eval "$(pyenv init -)"
```
and open a new terminal.

If you are still not running Python 3.10.8 take a look here: https://github.com/pyenv/pyenv/issues/660

5. Install `poetry`:

`pip install poetry==1.3.2`

6. Restart your terminal and make your virtual environtment:

`mkvirtualenv -p ~/.pyenv/versions/3.10.8/bin/python notifications-admin`

7. You can now return to your environment any time by entering

`workon notifications-admin`

8. Find the appropriate env variables and copy them into the .env file. A sane set of defaults exists in `.env.example` in the root folder. If you are working for CDS you should use the ones in the LastPass folder. If using from lastPass and running the API locally, change API_HOST_NAME to point to your local machine

9. Install all dependencies

`pip3 install -r requirements.txt`

10. Generate the version file ?!?

`make generate-version-file`

11. Generate the translations

`make babel`

12. Install npm and build the assets

`npm install` followed by `npm run build`

13.  Run the service

`flask run -p 6012 --host=localhost`

14. To test

`pip3 install -r requirements_for_test.txt`

`make test`


## Rebuilding the frontend assets

If you want the front end assets to re-compile on changes, leave this running
in a separate terminal from the app

```shell
    npm run watch
```


## Updating application dependencies

`poetry.lock` file is generated from the `pyproject.toml` in order to pin
versions of all nested dependencies. If `pyproject.toml` has been changed (or
we want to update the unpinned nested dependencies) `poetry.lock` should be
regenerated with

```
poetry lock --no-update
```

`poetry.lock` should be committed alongside `pyproject.toml` changes.


## Working with static assets

When running locally static assets are served by Flask at http://localhost:6012/static/…

When running on preview, staging and production there’s a bit more to it:

![notify-static-after](https://user-images.githubusercontent.com/355079/50343595-6ea5de80-051f-11e9-85cf-2c20eb3cdefa.png)


## Translations

- Wrap your template text

```
<h1>{{ _('Hello') }}</h1>
```

- For form hints

Set a variable

```
 <div class="extra-tracking">
  {% set hint_txt = _('We’ll send you a security code by text message') %}
  {{textbox(form.mobile_number, width='3-4', hint=hint_txt) }}
 </div>
```

For forms

```
from flask_babel import _
```

Wrap your text

```
_('Your text here')
```

For JavaScript

```
// add your text to main_template
window.APP_PHRASES = {
  now: "{{ _('Now') }}",
}
```

```
// in your JS file
let now_txt = window.polyglot.t("now");
```

- Extract

Currently this is a manual step. Add a row to `fr.csv` in `app/translations/csv/` for each new string you have wrapped. The format is: `"wrapped string","translation"`. Make sure the wrapped string you are adding is unique.

- Compile

```bash
make babel
```

- Testing

Some typos in the `fr.csv` file might not be caught by `babel` but will lead to incorrect or missing French text in the app. To test for the kinds of typos we’ve encountered before, run:
```bash
make test-translations
```
Note that this make target is always run during our CI process and will fail if any problems are detected when pushing changes.

## Using Local Jinja for testing template changes

See the [notification-api](https://github.com/cds-snc/notification-api) README for detailed instructions.

Template files used in this repo: `sms_preview_template.jinja2, email_preview_template.jinja2`

Note: Tests may break if `USE_LOCAL_JINJA_TEMPLATES` is set to `True` in your .env


## Redis

You need a [redis](https://redis.io/) server running to use certain parts of Notify, such as the "go live" flow. To use redis, add `REDIS_ENABLED=1` to your .env file and run the following command:

```bash
redis-server
```

## Testing

There are testing utilities available through the project.

### Feature flags

When developing new features, it is often useful to hide them behind a feature flag. This allows you to test the feature in a live environment without exposing it to all users. To create a feature flag, add a new key starting with `FF_` to the `.env` file.

The state of the various feature flags for staging and prod should be tracked within the `Test` and `ProductionFF` sections of `config.py`. This allows our CI workflows to run tests in both configurations to avoid regression issues in either environment.

### Trigger an exception on purpose

It is sometimes useful to trigger an exception for testing purposes (logger format,
multiline log behavior, etc.). To do so, you can hit the `_debug?key=DEBUG_KEY` endpoint.
The `DEBUG_KEY` should be defined in the environment's configuration, sourced at the
application' startup. When that endpoint is reached with the proper `DEBUG_KEY` secret,
a `500` HTTP error will be generated. When an incorrect or empty secret is provided, a classic '404'
not found error will get returned.

=======


# Notifications-admin

Application d'administration des notifications.

## Branche amont (_upstream_)

Ce dépôt Git est une version modifiée de :
https://github.com/alphagov/notifications-admin

## Caractéristiques de cette application

- Enregistrer et gérer les utilisateurs
- Créer et gérer des services
- Envoyer des courriels et des SMS par lots en téléversant un CSV
- Afficher l'historique des notifications

## Contraintes fonctionnelles

- Nous ne pouvons pas actuellement envoyer des lettres
- Nous ne pouvons pas savoir si les SMS ont été délivrés ou non

## Première mise en place

[Brew est un gestionnaire de paquets]((https://brew.sh/)) pour OSX. La commande suivante permet d'installer brew :
```shell
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Langages nécessaires
- Python 3.10
- [Node](https://nodejs.org/) 10.15.3 ou supérieur
- [npm](https://www.npmjs.com/) 6.4.1 ou plus
```shell
brew install node
```

[NPM](npmjs.org) est l'outil de gestion des paquets de Node. `n` est un outil de gestion des
différentes versions de Node. Ce qui suit installe `n` et utilise le support à long terme (LTS)
version de Node.
```shell
npm install -g n
n lts
npm rebuild node-sass
```

### Instruction d'installation locale

Sur macOS :

1. Installer PyEnv avec Homebrew. Cela vous permettra de préserver votre santé mentale.

`brew install pyenv`

2. Installez Python 3.10.8 ou la dernière version

`pyenv install 3.10.8`

3. Si vous n'attendez aucun conflit, mettez `3.10.8` comme valeur par défaut

`pyenv global 3.10.8`

4. Assurez-vous que la version 3.10.8 est maintenant la version par défaut en exécutant

`python --version`

Si ce n’est pas le cas, ajoutez les lignes suivantes à votre fichier shell rc. ex : `.bashrc` ou `.zshrc`
```
eval "$(pyenv init --path)"
eval "$(pyenv init -)"
```
et ouvrez un nouveau terminal.
Si vous n’utilisez toujours pas Python 3.10.8, jetez un coup d’œil ici : https://github.com/pyenv/pyenv/issues/660

5. Installez `virtualenv` :

`pip install virtualenvwrapper`

6. Ajoutez ce qui suit à votre `.bashrc` ou `.zshrc`

```
export WORKON_HOME=$HOME/.virtualenvs
export PROJECT_HOME=$HOME/Devel
source ~/.pyenv/versions/3.10.8/bin/virtualenvwrapper.sh
```

7. Redémarrez votre terminal et créez votre environnement virtuel :

`mkvirtualenv -p ~/.pyenv/versions/3.10.8/bin/python notifications-admin`

8. Vous pouvez maintenant retourner dans votre environnement à tout moment en entrant

`workon notifications-admin`

9. Trouvez les variables env appropriées et copiez-les dans le fichier .env. Un ensemble de valeurs par défaut existe dans le fichier `.env.example` à la racine ou vous pouvez utiliser celles du dossier LastPass. Si vous utilisez celles de LastPass et que vous exécutez l'API localement, modifiez `API_HOST_NAME` pour qu'elle pointe vers votre machine locale

10. Installer toutes les dépendances

`pip3 install -r requirements.txt`

11. Générer le fichier de version

`make generate-version-file`

12. Générer les traductions

`make babel`

13. Installer les dépendances npm et construire les actifs

`npm install` suivi de `npm run build`.

14.  Démarrer le service

`flask run -p 6012 --host=localhost`.

15. Pour tester

`pip3 install -r requirements_for_test.txt`

`make test`

## Reconstruire les fichiers CSS et JS du frontend

Si vous souhaitez que les fichier JS et CSS soient recompilés en fonction des changements, laissez tourner cette fonction dans un terminal séparé de l'application
```shell
npm run watch
```

## Mise à jour des dépendances des applications

Le fichier `requirements.txt` est généré à partir du fichier `requirements-app.txt` afin d'épingler des versions de toutes les dépendances imbriquées. Si `requirements-app.txt` a été modifié (ou nous voulons mettre à jour les dépendances imbriquées non épinglées) `requirements.txt` devrait être régénérée avec

```
make freeze-requirements
```

Le fichier `requirements.txt` doit être ajouté en même temps que les modifications du fichier `requirements-app.txt`.


## Travailler avec des fichier statiques

Lorsque utilisé localement, les fichiers statiques sont servis par Flask à http://localhost:6012/static/...

Lorsque en production ou sur staging, c'est un peu plus compliqué:

![notify-static-after](https://user-images.githubusercontent.com/355079/50343595-6ea5de80-051f-11e9-85cf-2c20eb3cdefa.png)


## Traductions

- Le texte dans le code est en anglais
- Enveloppez votre texte avec `{{ }}`
- Les traductions sont dans `app/translations/csv/fr.csv`

```
<h1>{{ _('Hello') }}</h1>
```

- Pour des conseils sur les formulaires

Crée une variable

```
 <div class="extra-tracking">
  {% set hint_txt = _('We’ll send you a security code by text message') %}
  {{textbox(form.mobile_number, width='3-4', hint=hint_txt) }}
 </div>
```

Pour les formulaires

```
from flask_babel import _
```

Enveloppez votre texte
```
_("Votre texte ici")
```

Pour JavaScript

```
// ajoutez votre texte au main_template
window.APP_PHRASES = {
  now: "{{ _('Now') }}",
}
```

```
// dans vos fichier JS
let now_txt = window.polyglot.t("now") ;
```

- Extrait

Actuellement, il s'agit d'une étape manuelle. Ajoutez une ligne à `fr.csv` dans `app/translations/csv/` pour chaque nouvelle  de charactère que vous avez enveloppée. Le format est le suivant : `"Texte Anglais", "traduction"`. Assurez-vous que la chaîne enveloppée que vous ajoutez est unique.

- Compiler

```Bash
make babel
```

- Tester

Certaines erreurs de frappe dans le fichier `fr.csv` pourraient ne pas être détectées par `babel` mais entraîneraient des changements incorrects ou du texte manquant en français dans l’application. Pour tester contre ces types d’erreurs de frappe qu’on a vu dans le passé, exécutez :
```bash
make test-translations
```
Cette cible make est toujours exécutée pendant le processus d’intégration continue et échouera si des problèmes sont détectés lorsqu’on pousse le code.

## Utiliser Jinja localement pour tester les changements de modèles

Voir le dépôt [notification-api](https://github.com/cds-snc/notification-api) README pour des instructions détaillées.

Fichiers de modèles utilisés dans ce dépôt : `sms_preview_template.jinja2, email_preview_template.jinja2`

Note : les tests peuvent échouer si `USE_LOCAL_JINJA_TEMPLATES` est réglé sur `True` dans votre `.env`

## Tests

Il y a quelques utilitaires de tests qui sont disponibles dans le projet.

### Déclencher une erreur de façon intentionnelle

Il est quelques fois pratique de déclencher une erreur pour des buts de tests (format
du log, comportement multiligne du log, etc.). Pour se faire, vous pouvez accéder à l'URL
`_debug?key=DEBUG_KEY`. Le secret `DEBUG_KEY` devrait être défini dans la configuration
de l'environnement lors du démarrage de l'application. Quand cet URL sera accédé avec
le bon secret `DEBUG_KEY`, une erreur HTTP `500` sera générée. Sans ce secret ou avec
une valeur invalide, une erreur `404` de page non-trouvée sera alors produite.
