# Career Copilot — Manuel David Maya Rosero

Aplicación local para transformar una oferta de trabajo en una candidatura completa:

- analiza el idioma y los requisitos de la oferta;
- cruza automáticamente la oferta con el perfil profesional verificado;
- genera un CV LaTeX de una página con el formato del CV original;
- genera una carta de motivación en francés, inglés o español;
- registra la candidatura, entrevistas y seguimientos;
- exporta todo a `seguimiento_candidaturas.xlsx`.

El CV y la carta solo se pueden descargar. La aplicación no incluye un editor de documentos. El perfil profesional maestro sí es editable y se utiliza como fuente para las siguientes candidaturas.

## Contenido importado

El perfil inicial se genera desde:

`D:/Escritorio/MyPage/manuelma4.github.io/assets/js/content.js`

La importación actual incluye las experiencias, formación, proyectos, tecnologías, certificaciones e idiomas presentes en el portafolio. Para actualizar el snapshot después de cambiar la web:

```powershell
node .\scripts\import_portfolio.mjs "D:\Escritorio\MyPage\manuelma4.github.io\assets\js\content.js"
```

Después, en la aplicación, se puede usar **Restaurar desde el portafolio**.

Las cartas DOCX adjuntas se importan como referencias de tono —nunca como fuente de hechos— mediante:

```powershell
.\.venv\Scripts\python.exe .\scripts\import_documents.py `
  "D:\Escritorio\Works\lettre_de_motivation_Manuel David Maya Rosero(manueldmaya@gmail.com).docx" `
  "D:\Escritorio\Works\motivation_letter_Manuel_Maya(manueldmaya@gmail.com).docx"
```

## Iniciar la aplicación

La forma más sencilla es ejecutar:

```text
start-app.cmd
```

Después abre [http://127.0.0.1:8000](http://127.0.0.1:8000).

También se puede iniciar desde PowerShell:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Activar la generación con OpenAI

Sin una API key, la aplicación funciona en modo local: selecciona experiencias y tecnologías mediante coincidencias verificables y compila los documentos en LaTeX.

Para utilizar la generación estructurada, copia `.env.example` como `.env` y añade una clave de proyecto:

```dotenv
OPENAI_API_KEY=tu_clave
OPENAI_MODEL=gpt-5.6-terra
```

La clave permanece en el backend y nunca se entrega al navegador. Cuando la IA está activada, el texto de la oferta y el perfil profesional se envían al proveedor para generar los documentos.

## Instalación reproducible

El entorno actual ya contiene Python 3.12, MiKTeX/XeLaTeX, Node 24 y las dependencias Python. Para recrear el entorno:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Raleway y su licencia OFL están incluidas en `app/latex/fonts`, por lo que los PDF mantienen la tipografía sin depender de fuentes instaladas en Windows.

## Verificación

```powershell
$env:DATABASE_URL='sqlite:///D:/Escritorio/Works/Works/.tmp-tests/test.db'
$env:GENERATED_DIR='D:/Escritorio/Works/Works/.tmp-tests/generated'
$env:OPENAI_API_KEY=''
.\.venv\Scripts\python.exe -X utf8 -m tests.smoke_api
```

La prueba valida el recorrido oferta → API → base de datos → CV PDF → carta PDF → Excel y confirma que ambos documentos tienen una sola página.
