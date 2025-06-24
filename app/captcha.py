#------------------------ IMPORTS --------------------------#
from __future__ import annotations

from . import *
from .utils import debugger
from .menu import NotificationPriority
from requests import post, exceptions
from threading import Thread
from time import sleep
from json import loads
from re import sub

#------------------------ CONSTANTS --------------------------#
MAX_CAPTCHA_REGENS = 3

#------------------------- CLASSES ---------------------------#
class UnkownCaptchaError(Exception):
    pass

#Todo: make a captcha status (like scheduler class)


@dataclass
class Captcha:
    '''Catpcha class, detects and solves captchas.'''
    #Todo: split this class in chaptcha "controller" and captcha datatype
    #Pointers
    menu: BaseMenu = field(repr=False)
    
    #Components
    answers: list = field(default_factory=list)
    captcha_image: str = None
    
    #Backend
    _word_list: list[str] = field(init=False, repr=False)
    _captcha_length: int = 6
    
    #Counters
    regens: int = 0
    
    #Flags
    busy: bool = False
    detected: bool = False
    solving: bool = False
    regenerating: bool = False

    #OCR Settings
    is_overlay_required: bool = field(default=False, repr=False)
    detect_orientation: bool = field(default=True, repr=False)
    scale: bool = field(default=False, repr=False)
    language: str = field(default='eng', repr=False)
    
    def __post_init__(self) -> None:
        self._word_list = ['captcha', 'verify']
        self._engines = [2, 1, 3, 5]
    
    @property
    def name(self) -> str:
        '''Returns the class name in the correct format.'''
        return f'{self.__class__.__name__}'
    
    def filter(self, value: str) -> str:
        '''Filters results form the API. Valid results -> only alphanum and len == 6'''
        if value:
            ans = sub('[^a-zA-Z0-9]', '', value)
            if len(ans) == self._captcha_length:
                return ans
            else: 
                #Invalid result
                return None
        else:
            return None
    
    def request(self, engine: int) -> None:
        #Todo: make this function less complex and better structured
        '''Makes a request to the OCR api and appends the result (if valid) to the answers list.'''
        if not self.detected: 
            return None

        payload = {
            'apikey': self.api_key,
            'url': self.captcha_image,
            'isOverlayRequired': self.is_overlay_required,
            'detectOrientation': self.detect_orientation,
            'scale': self.scale,
            'OCREngine': engine,
            'language': self.language
        }
        
        try:
            request = post(self._ocr_url, data=payload, timeout=self._max_timeout)
            response = loads(request.content.decode())
        except exceptions.ReadTimeout as e:
            #Took too long to respond
            self.menu.notify(f'[!] Engine {engine} took too long to respond.', NotificationPriority.LOW)
            if engine == self._engines[-1]:
                self.solving = False
            debugger.log(e, f'{self.name} - request timeout | {self}')
            return None
        except Exception as e:
            debugger.log(e, f'{self.name} - request')
            raise UnkownCaptchaError(e)
        
        if response['OCRExitCode'] == 1:
            if self.detected:
                answer = self.filter(response['ParsedResults'][0]['ParsedText'])
                if answer:
                    #To avoid conflicts due to multi-threading, it must not be duplicate, 
                    #it must not be solved and must be busy (to garatee that the object it's the same)
                    if answer not in self.answers and self.detected:
                        self.answers.append(answer)
                    else:
                        #Duplicate result
                        pass
            
            if engine == self._engines[-1]:
                if not self.detected: 
                    return None
                self.solving = False
            return None
        else:
            #API error
            if not self.detected: 
                return None
            self.menu.notify(
                f'[!] Engine {engine} OCR API error -> ExitCode: {response["OCRExitCode"]}.', 
                NotificationPriority.HIGH
            )
            if engine == self._engines[-1]:
                self.solving = False
            return None     
            
    def detect(self, event: dict) -> bool:
        '''Attempts to detect any captchas in the event. Only triggers if a keyword is present AND an embed with an image exists.'''
        self.busy = True
        self.detected = False

        # Check for embeds with images
        embeds = event.get('embeds', [])
        if not embeds:
            self.busy = False
            self.reset()
            return False

        # Check for keywords in the event
        found_keyword = any(target in str(event).lower() for target in self._word_list)
        if not found_keyword:
            self.busy = False
            self.reset()
            return False

        # Now check for an image in the embed
        for embed in embeds:
            image_url = embed.get('image', {}).get('url')
            if image_url:
                self.captcha_image = image_url
                self.detected = True
                self.busy = False
                return True

        # If no image found, not a captcha
        self.busy = False
        self.reset()
        return False

    def solve(self) -> None:
        '''No-op: API-based captcha solving removed.'''
        self.busy = False
        self.solving = False
        self.regenerating = False
        self.answers = []
        return None
    
    def reset(self) -> None:
        '''Reset all attrs to default values.'''
        self.answers = []
        self.busy = False
        self.detected = False
        self.regenerating = False
        self.regens = 0
        return None
        
        
# --------- INIT ---------#
if __name__ == "__main__":
    pass