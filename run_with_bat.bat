set PYTHONPATH=.;./src/aceinna/devices/widgets;%PYTHONPATH%

python main.py -i canfd %2

@echo kill python driver...