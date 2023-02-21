import os

import nbformat
from nbconvert.preprocessors import ExecutePreprocessor, CellExecutionError

processor = ExecutePreprocessor(timeout=600, kernel_name='python')

with open(os.environ.get('SCRIPT_PATH', 'script.ipynb')) as f:
    notebook = nbformat.read(f, as_version=4)

last_logs_file = 'script.log'


def execute_notebook():
    try:
        processor.preprocess(notebook)
    except CellExecutionError:
        msg = 'Error executing the notebook.\n\n'
        msg += 'See notebook "%s" for the traceback.' % last_logs_file
        print(msg)
        raise
    finally:
        with open(last_logs_file, mode='w', encoding='utf-8') as f:
            nbformat.write(notebook, f)


if __name__ == "__main__":
    execute_notebook()
