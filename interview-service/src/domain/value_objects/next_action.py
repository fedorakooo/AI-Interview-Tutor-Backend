from src.domain.value_objects.ask_focus import AskFocus
from src.domain.value_objects.ask_intro import AskIntro
from src.domain.value_objects.complete import Complete

NextAction = AskIntro | AskFocus | Complete
