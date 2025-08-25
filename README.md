# Architecture

## Core Component Breakdown

**main.py**: Its only job is to create an instance of the GameManager and start the game. Simple and clean.

**config.json**: A plain text file where you can easily change game rules without touching the code. We'll set it up with the options you requested.

**GameManager**: The "brain" of the game. It will initialize the UI, load player data, and control the flow from the main menu to level selection and gameplay.

**KeyboardManager**: A crucial component for your setup. It will be responsible for the initial "press a key" screen to identify which keyboard belongs to which player.

**LevelManager**: This will read the "letters" or "words" stream and know which level comes next. It will feed the correct letters/words to the game screen.

**UIManager**: This handles all the visual aspects. It will create the two main windows and be responsible for drawing the text, coloring the letters green/red, and displaying the stats screens.


# Installation

Create virtual environment:
```
python3 -m venv ./venv
```

Activate the environment:
```
source ./venv/bin/activate
```

Install dependencies:
```
sudo apt-get install python3-tk
pip install evdev 
```

Run:
```
sudo python3 src/tt.py
```
