# How to contribute to satComTopology 🔨

The project issues are available [here](https://github.com/elbarbi/satComTopology/issues).

## Install the project 📜
### Clone the project
```shell
git clone https://github.com/elbarbi/satComTopology.git satComTopology
cd satComTopology
```
### Install your workspace
#### Init your virtual environment 🐍
[Virtual Env full documentation](https://docs.python.org/fr/3/library/venv.html)
```sh
python -m venv .venv
```
#### Activate your virtual environment
```shell
source .venv/bin/activate
```
#### Install dependencies
```shell
pip install -r requirements.txt
```
## Start contributing ⚒️
- Choose your issue
- Make sure you are in the develop branch; Execute the following command, your current branch should be underlined.
```shell
git branch
```
- Make sure it is the last version
```shell
git pull
```
- Create a branch with the issue slug (dbetter to do do it from the GitHub app)
```shell
git checkout -b #{issue_number}-issue-title-separeted-with-dashes
```
- You can start coding !

## Contributing rules 🚨
### Make your code readable 🔍
Reading [this](https://en.wikipedia.org/wiki/Coding_best_practices) is a good start.
Example:
**Don't** do this:
```python
s = SimulationManager()

sat1 = Satellite()
sat2 = Satellite()

if sat1.object_id == sat2.object_id and sat1.name == sat2.name:
  # Do your things
```
**Do this**:
```python
simulation_manager = SimulationManager()

current_satellite = Satellite()
target_satellite = Satellite()

satellites_have_same_id = current_satellite.object_id == target_satellite.object_id
satellites_have_same_name = current_satellite.name == target_satellite.name

satellites_are_the_same = satellites_have_same_id and satellites_have_same_name

if satellites_are_the_same:
  # Do your things
```
### Type everything
Python include typing. You have to type variables in method, function and classes.
[Documentation here](https://docs.python.org/3/library/typing.html).
### Make your documentation 📋
```python
def my_function(param_1: str, param_2: int) -> int:
    """
    Description of your function.
    :param param_1: A string variable that will ...
    :param param_2: An integer that will ...
    :return: An integer that is ...
    """
```
## When you are done
- Push your code.
```shell
git push
```
- Create a pull request from the user interface.
- Resolve conflicts.
- Wait for the maintainer approval.

