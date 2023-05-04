


"""
get_nocrash_lines() 
    
    Identifies which lines will not cause a crash when evaulated via cheetah templating.

    Using CheetahBlocks, we evaluate each segment of code, then if it doesn't cause a crash, we add it to the output. 

    Because some previous lines might be important for the current block, we concat the current block to all previous lines which haven't yet caused a crash. 

    For example in the following text:
    ```
    #set mystr = 'hello'
    #set mystr2 = mystr + ' there!'
    
    #if mystr2 == 'hello there!':
        'it worked :)'
    #else
        'it didnt work :('
    ```

    The following CheetahBlocks will be created
    block1: ["#set mystr = 'hello'"]
    block2: ["#set mystr2 = mystr + ' there!'"]
    block3: [
        "#if mystr2 == 'hello there!':",
        "'it worked :)'",
        "#else",
        "'it didnt work :('",
    ]

    when we evaluate block1, it wont crash since it's just a variable assignment.
    when we evaluate block2, it will crash since `mystr` isnt defined. 

    therefore when evaluating block2, we include block1 since it didnt crash.
    this means block2 is now 
        #set mystr = 'hello'
        #set mystr2 = mystr + ' there!'

    when running this, it will not crash because the previous line is included. 

    for evaluating block3 we will now evaluate:
        #set mystr = 'hello'
        #set mystr2 = mystr + ' there!'
        
        #if mystr2 == 'hello there!':
            'it worked :)'
        #else
            'it didnt work :('

    which will again, not crash because mystr2 is defined. 

    we make our way down the text, producing the list of lines which will not cause a crash. 

"""


"""
TODO 
# ensure same number of lines in input and output
# recursive evaluation

"""


from typing import Any
from .detection import CheetahNoCrashDetector
from ..common.aliases import extract_associations
from ..common.aliases import resolve_associations
from Cheetah.Template import Template
from galaxy.util import unicodify


def cheetah_evaulate(text: str, input_dict: dict[str, Any]) -> str:
    try:
        return cheetah_evaulate_risky(text, input_dict)
    except Exception as e:
        return cheetah_evaulate_safe(text, input_dict)


def cheetah_evaulate_risky(text: str, input_dict: dict[str, Any]) -> str:
    # find any local variables associated with step inputs
    alias_register = extract_associations(text, input_dict)
    
    # resolve those local variables to the step input they are associated with
    resolved_text = resolve_associations(text, alias_register)
    print(resolved_text)
    
    # get the lines which don't cause a cheetah crash
    nocrash_text = get_nocrash_text(resolved_text, input_dict)
    print(nocrash_text)
    
    # evaluate the final text
    evaluated_text = evaluate_final_text(nocrash_text, input_dict)
    print(evaluated_text)
    return evaluated_text

def cheetah_evaulate_safe(text: str, input_dict: dict[str, Any]) -> str:
    # get the lines which don't cause a cheetah crash
    nocrash_text = get_nocrash_text(text, input_dict)
    print(nocrash_text)
    
    # find any local variables associated with step inputs
    alias_register = extract_associations(nocrash_text, input_dict)
    
    # resolve those local variables to the step input they are associated with
    resolved_text = resolve_associations(nocrash_text, alias_register)
    print(resolved_text)

    # evaluate the final text
    evaluated_text = evaluate_final_text(resolved_text, input_dict)
    print(evaluated_text)
    return evaluated_text

def get_nocrash_text(text: str, input_dict: dict[str, Any]) -> str:
    """
    (stage1)
    detect which lines will not cause a cheetah crash.
    other lines are masked out.
    """
    all_lines = text.splitlines()
    detector = CheetahNoCrashDetector(all_lines, input_dict)
    outcome = detector.detect()
    return '\n'.join(outcome)

def evaluate_final_text(text: str, input_dict: dict[str, Any]) -> str:
    # which lines are ok to evaluate?
    # aliases -> reassign local vars to tool inputs
    t = Template(source=text, namespaces=[input_dict])
    out = str(unicodify(t))
    return out



