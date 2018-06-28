from google.cloud import speech
from google.oauth2 import service_account
from threading import Thread

class GoogleSTT:
    def __init__(self, language, cred_json_path):
        creds = service_account.Credentials.from_service_account_file(cred_json_path)
        self._client = speech.SpeechClient(credentials=creds)
        config = speech.types.RecognitionConfig(
            encoding='LINEAR16',
            language_code=language,
            sample_rate_hertz=16000)
        self._config = speech.types.StreamingRecognitionConfig(config=config, interim_results=True)
        self._callback = None

    def setCallback(self, callback):
        self._callback = callback

    def startRecognize(self, generator, id=0):
        requests = (speech.types.StreamingRecognizeRequest(audio_content=content)
                    for content in generator)
        responses = self._client.streaming_recognize(self._config, requests)
        Thread(target=self._response_handler, args=(responses, id)).start()

    def _response_handler(self, responses, id):
        previous = ""
        for resp in responses:
            if not resp.results:
                continue
            result = resp.results[0]
            if not result.alternatives:
                continue
            text = result.alternatives[0].transcript
            if result.is_final:
                self._callback(text, result.alternatives[0].confidence, id)
            elif result.stability > 0.5:
                if text != previous:
                    previous = text
                    self._callback(text, 0.0, id)