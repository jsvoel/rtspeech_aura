#!/usr/bin/env python

import rospy
from rtspeech_aura.msg import RealtimeTranscript
from rtspeech_aura.srv import setMicrophoneMuteState, getMicrophoneMuteState

from googlespeech import GoogleSTT
from micreader import MicReader
from unicodereplace import asciiFixerFactory

loglevel = rospy.get_param('/debug/loglevel', rospy.INFO)
rospy.init_node('rtspeechv2', anonymous=False, log_level=loglevel)

credfilepath = rospy.get_param(rospy.get_namespace() + 'stt_cred', '/home/corobi/.cloudkeys/robostt_cred.json')
language = rospy.get_param(rospy.get_namespace() + 'language', 'en-US')
micbuffersize = rospy.get_param(rospy.get_namespace() + 'micbuffer', 0.8)
vadattack = rospy.get_param(rospy.get_namespace() + 'vad_attack', 0.18)
vadhold = rospy.get_param(rospy.get_namespace() + 'vad_hold', 1.0)
vadaggro = rospy.get_param(rospy.get_namespace() + 'vad_aggro', 0)

rtpub = None
gstt = None
micr = None
micmute = False

asciifix = asciiFixerFactory(language)

def main():
    global rtpub
    global gstt
    global micr


    rtpub = rospy.Publisher(rospy.get_namespace() + 'realtimetranscript', RealtimeTranscript, queue_size=10)

    micr = MicReader(None, micbuffersize, vadcallback, vadattack, vadhold, vadaggro, False)
    micr.start()
    gstt = GoogleSTT(language, credfilepath)
    gstt.setCallback(transcriptcallback)

    mss = rospy.Service(rospy.get_namespace() + 'setmicrophonemutestate', setMicrophoneMuteState, setMicMute)
    mgs = rospy.Service(rospy.get_namespace() + 'getmicrophonemutestate', getMicrophoneMuteState, getMicMute)

    while not rospy.is_shutdown():
        try:
            rospy.spin()
        except:
            pass

    rospy.loginfo("rtspeech node shutdown")

def transcriptcallback(text, confidence, direction):
    text = asciifix(text)
    tsmsg = RealtimeTranscript()
    tsmsg.text = text
    tsmsg.direction = direction
    rospy.loginfo(u"{}: {}".format(confidence, text))
    tsmsg.confidence = confidence
    if confidence != 0.0:
        tsmsg.final = True
    rtpub.publish(tsmsg)

def vadcallback(speech_detected):
    rospy.loginfo(u"Speech detected: {}  |  Muted: {}".format(speech_detected, micmute))
    if not micmute and speech_detected:
        gstt.startRecognize(micr.start_generation(), 0)
    else:
        micr.stop_generation()

def setMicMute(request):
    global micmute
    prev = micmute
    micmute = request.muted
    if micmute:
        micr.stop_generation() # stop ongoing transmission upon mute
    return prev

def getMicMute(request):
    return micmute

main()
