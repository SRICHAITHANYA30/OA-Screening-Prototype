from __future__ import annotations

import json
import random
import time
from typing import Any


NER_EMOJI = {
    "flowers": ["\U0001F338", "\U0001F33A", "\U0001F337", "\U0001F33B", "\U0001F33C", "\U0001F490", "\U0001F339", "\U0001FAB7"],
    "animals": ["\U0001F418", "\U0001F98F", "\U0001F403", "\U0001F99A", "\U0001F412", "\U0001F40A", "\U0001F405", "\U0001F43B"],
    "festivals": ["\U0001FA94", "\U0001F389", "\U0001F38A", "\U0001FA85", "\U0001F38B", "\U0001F3EE", "\U0001F3AA", "\U0001F3AD"],
    "food": ["\U0001F35A", "\U0001F35B", "\U0001FAD6", "\U0001F958", "\U0001F361", "\U0001F358", "\U0001F957", "\U0001F9C1"],
    "nature": ["\U0001F3D4", "\U0001F30A", "\U0001F333", "\U0001F319", "\U0001F31E", "\U0001F308", "\U0001F327", "\U0001F976"],
}

NER_THEME_NAMES = {
    "flowers": {
        "en": ["Lotus", "Hibiscus", "Tulip", "Sunflower", "Daisy", "Bouquet", "Rose", "Water Lily"],
        "hi": ["\u0915\u092e\u0932", "\u0917\u0941\u0932\u093e\u092c", "\u091f\u094d\u092f\u0942\u0932\u093f\u092a", "\u0938\u0942\u0930\u091c\u092e\u0941\u0916\u0940", "\u0917\u0941\u0932\u0926\u0938\u094d\u0924\u093e", "\u092b\u0942\u0932", "\u0917\u0941\u0932\u093e\u092c", "\u091c\u0932 \u0915\u092e\u0932"],
        "bn": ["\u0995\u09ae\u09b2", "\u0997\u09c1\u09b2\u09be\u09ac", "\u099f\u09bf\u0989\u09b2\u09bf\u09aa", "\u09b8\u09c2\u09b0\u09cd\u09af\u09ae\u09c1\u0996\u09c0", "\u09a1\u09c7\u0987\u099a\u09bf", "\u09ab\u09c1\u09b2\u09a6\u09be\u09a8\u09c0", "\u0997\u09c1\u09b2\u09be\u09ac", "\u099c\u09b2 \u0995\u09ae\u09b2"],
        "as": ["\u0995\u09ae\u09b2", "\u0997\u09c1\u09b2\u09be\u09ac", "\u099f\u09bf\u0989\u09b2\u09bf\u09aa", "\u09b8\u09c2\u09b0\u09cd\u09af\u09ae\u09c1\u0996\u09c0", "\u09a1\u09c7\u0987\u099a\u09bf", "\u09ab\u09c1\u09b2\u09a6\u09be\u09a8\u09c0", "\u0997\u09c1\u09b2\u09be\u09ac", "\u099c\u09b2 \u0995\u09ae\u09b2"],
    },
    "animals": {
        "en": ["Elephant", "Rhino", "Buffalo", "Peacock", "Monkey", "Crocodile", "Tiger", "Bear"],
        "hi": ["\u0939\u093e\u0925\u0940", "\u0917\u0948\u0902\u0921\u093e", "\u092d\u0948\u0902\u0938", "\u092e\u094b\u0930", "\u092c\u0902\u0926\u0930", "\u092e\u0917\u0930\u092e\u091b\u094d\u091b", "\u092c\u093e\u0918", "\u092d\u093e\u0932\u0942"],
        "bn": ["\u09b9\u09be\u09a4\u09bf", "\u0997\u09cb\u09a8\u09cd\u09a1\u09be", "\u09ae\u09b9\u09bf\u09b7", "\u09ae\u09af\u09bc\u09c2\u09b0", "\u09ac\u09be\u09a8\u09b0", "\u0995\u09c1\u09ae\u09bf\u09b0", "\u09ac\u09be\u0998", "\u09ad\u09be\u09b2\u09c1\u0995"],
        "as": ["\u09b9\u09be\u09a4\u09bf", "\u0997\u09c7\u0981\u09a1\u09bc\u09be", "\u09ae\u09b9\u09c0", "\u09ae\u09af\u09bc\u09c2\u09b0", "\u09ac\u09be\u09a8\u09b0", "\u0995\u09c1\u09ae\u09bf\u09b0", "\u09ac\u09be\u0998", "\u09ad\u09be\u09b2\u09c1\u0995"],
    },
    "festivals": {
        "en": ["Diwali", "Bihu", "Christmas", "Eid", "Pongal", "Navratri", "Holi", "Baisakhi"],
        "hi": ["\u0926\u0940\u092a\u093e\u0935\u0932\u0940", "\u092c\u093f\u0939\u0942", "\u0915\u094d\u0930\u093f\u0938\u092e\u0938", "\u0908\u0926", "\u092a\u094b\u0902\u0917\u0932", "\u0928\u0935\u0930\u093e\u0924\u094d\u0930\u093f", "\u0939\u094b\u0932\u0940", "\u092c\u0948\u0938\u093e\u0916\u0940"],
        "bn": ["\u09a6\u09c0\u09aa\u09be\u09ac\u09b2\u09c0", "\u09ac\u09bf\u09b9\u09c2", "\u0995\u09cd\u09b0\u09bf\u09b8\u09ae\u09b8", "\u0988\u09a6", "\u09aa\u09cb\u0982\u0997\u09b2", "\u09a8\u09ac\u09b0\u09be\u09a4\u09cd\u09b0\u09bf", "\u09b9\u09cb\u09b2\u09c0", "\u09ac\u09c8\u09b8\u09be\u0996\u09c0"],
        "as": ["\u09a6\u09c0\u09aa\u09be\u09ac\u09b2\u09c0", "\u09ac\u09bf\u09b9\u09c1", "\u0995\u09cd\u09b0\u09bf\u09b8\u09ae\u09b8", "\u0988\u09a6", "\u09aa\u09cb\u0982\u0997\u09b2", "\u09a8\u09ac\u09b0\u09be\u09a4\u09cd\u09b0\u09bf", "\u09b9\u09cb\u09b2\u09c0", "\u09ac\u09c8\u09b8\u09be\u0996\u09c0"],
    },
    "food": {
        "en": ["Rice", "Curry", "Tea", "Stew", "Dumpling", "Rice Cake", "Salad", "Sweet"],
        "hi": ["\u091a\u093e\u0935\u0932", "\u0938\u092c\u094d\u091c\u0940", "\u091a\u093e\u092f", "\u0938\u094d\u091f\u094d\u092f\u0942", "\u092e\u094b\u092e\u094b", "\u091a\u093e\u0935\u0932 \u0915\u0947\u0915", "\u0938\u0932\u093e\u0926", "\u092e\u093f\u0920\u093e\u0908"],
        "bn": ["\u099a\u09be\u0989\u09b2", "\u09a4\u09b0\u0995\u09be\u09b0\u09c0", "\u099a\u09be", "\u09b8\u09cd\u099f\u09c1", "\u09ae\u09cb\u09ae\u09cb", "\u099a\u09be\u0989\u09b2\u09c7\u09b0 \u0995\u09c7\u0995", "\u09b8\u09be\u09b2\u09be\u09a1", "\u09ae\u09bf\u09a0\u09be\u0987"],
        "as": ["\u09ad\u09be\u09a4", "\u09a4\u09b0\u0995\u09be\u09b0\u09c0", "\u099a\u09be\u09b9", "\u09b8\u09cd\u099f\u09c1", "\u09ae\u09cb\u09ae\u09cb", "\u09ad\u09be\u09a4\u09c7\u09b0 \u0995\u09c7\u0995", "\u09b8\u09be\u09b2\u09be\u09a1", "\u09ae\u09bf\u09a0\u09be\u0987"],
    },
    "nature": {
        "en": ["Mountain", "River", "Tree", "Moon", "Sun", "Rainbow", "Rain", "Snow"],
        "hi": ["\u092a\u0939\u093e\u0921\u093c", "\u0928\u0926\u0940", "\u092a\u0947\u0921\u093c", "\u091a\u093e\u0901\u0926", "\u0938\u0942\u0930\u091c", "\u0907\u0902\u0926\u094d\u0930\u0927\u0928\u0941\u0937", "\u092c\u093e\u0930\u093f\u0936", "\u092c\u0930\u094d\u092b"],
        "bn": ["\u09aa\u09be\u09b9\u09be\u09a1\u09bc", "\u09a8\u09a6\u09c0", "\u0997\u09be\u099b", "\u099a\u09be\u0981\u09a6", "\u09b8\u09c2\u09b0\u09cd\u09af", "\u09b0\u09be\u09ae\u09a7\u09a8\u09c1", "\u09ac\u09c3\u09b7\u09cd\u099f\u09bf", "\u09ac\u09b0\u09cd\u09ab"],
        "as": ["\u09aa\u09be\u09b9\u09be\u09f0", "\u09a8\u09a6\u09c0", "\u0997\u09be\u099b", "\u099a\u09be\u0981\u09a6", "\u09b8\u09c2\u09f0\u09cd\u09af", "\u09f0\u09be\u09ae\u09a7\u09a8\u09c1", "\u09ac\u09c3\u09b7\u09cd\u099f\u09bf", "\u09ac\u09b0\u09cd\u09ab"],
    },
}


DAILY_ROUTINE_ACTIVITIES = {
    "en": [
        {"id": "wake", "text": "Wake up and get out of bed", "emoji": "\U0001F305", "typical_hour": 6},
        {"id": "wash", "text": "Brush teeth and wash face", "emoji": "\U0001FA65", "typical_hour": 6},
        {"id": "bath", "text": "Take a bath", "emoji": "\U0001F6BF", "typical_hour": 7},
        {"id": "breakfast", "text": "Have breakfast", "emoji": "\U0001F373", "typical_hour": 8},
        {"id": "med1", "text": "Take morning medicine", "emoji": "\U0001F48A", "typical_hour": 8},
        {"id": "walk", "text": "Go for a walk", "emoji": "\U0001F6B6", "typical_hour": 9},
        {"id": "lunch", "text": "Have lunch", "emoji": "\U0001F35A", "typical_hour": 12},
        {"id": "rest", "text": "Afternoon rest", "emoji": "\U0001F4A4", "typical_hour": 14},
        {"id": "tea", "text": "Evening tea", "emoji": "\U0001FAD6", "typical_hour": 16},
        {"id": "prayer", "text": "Prayer or meditation", "emoji": "\U0001F64F", "typical_hour": 18},
        {"id": "dinner", "text": "Have dinner", "emoji": "\U0001F35B", "typical_hour": 19},
        {"id": "med2", "text": "Take night medicine", "emoji": "\U0001F48A", "typical_hour": 21},
        {"id": "sleep", "text": "Go to sleep", "emoji": "\U0001F319", "typical_hour": 22},
    ],
    "hi": [
        {"id": "wake", "text": "\u0938\u0941\u092c\u0939 \u0909\u0920\u0947\u0902", "emoji": "\U0001F305", "typical_hour": 6},
        {"id": "wash", "text": "\u0926\u093e\u0901\u0924 \u0938\u093e\u092b \u0915\u0930\u0947\u0902", "emoji": "\U0001FA65", "typical_hour": 6},
        {"id": "bath", "text": "\u0928\u0939\u093e\u090f\u0901", "emoji": "\U0001F6BF", "typical_hour": 7},
        {"id": "breakfast", "text": "\u0928\u093e\u0936\u094d\u0924\u093e \u0915\u0930\u0947\u0902", "emoji": "\U0001F373", "typical_hour": 8},
        {"id": "med1", "text": "\u0938\u0941\u092c\u0939 \u0915\u0940 \u0926\u0935\u093e \u0932\u0947\u0902", "emoji": "\U0001F48A", "typical_hour": 8},
        {"id": "walk", "text": "\u0938\u0948\u0930 \u0915\u094b \u091c\u093e\u090f\u0901", "emoji": "\U0001F6B6", "typical_hour": 9},
        {"id": "lunch", "text": "\u0926\u094b\u092a\u0939\u0930 \u0915\u093e \u0916\u093e\u0928\u093e \u0916\u093e\u090f\u0901", "emoji": "\U0001F35A", "typical_hour": 12},
        {"id": "rest", "text": "\u0906\u0930\u093e\u092e \u0915\u0930\u0947\u0902", "emoji": "\U0001F4A4", "typical_hour": 14},
        {"id": "tea", "text": "\u0936\u093e\u092e \u0915\u0940 \u091a\u093e\u092f", "emoji": "\U0001FAD6", "typical_hour": 16},
        {"id": "prayer", "text": "\u092a\u0942\u091c\u093e \u092f\u093e \u0927\u094d\u092f\u093e\u0928", "emoji": "\U0001F64F", "typical_hour": 18},
        {"id": "dinner", "text": "\u0930\u093e\u0924 \u0915\u093e \u0916\u093e\u0928\u093e \u0916\u093e\u090f\u0901", "emoji": "\U0001F35B", "typical_hour": 19},
        {"id": "med2", "text": "\u0930\u093e\u0924 \u0915\u0940 \u0926\u0935\u093e \u0932\u0947\u0902", "emoji": "\U0001F48A", "typical_hour": 21},
        {"id": "sleep", "text": "\u0938\u094b\u0915\u0947 \u091c\u093e\u090f\u0901", "emoji": "\U0001F319", "typical_hour": 22},
    ],
    "bn": [
        {"id": "wake", "text": "\u098f\u0995\u09c1\u09a8 \u0989\u09a0\u09c1\u09a8", "emoji": "\U0001F305", "typical_hour": 6},
        {"id": "wash", "text": "\u09a6\u09be\u0981\u09a4 \u09ae\u09be\u099c\u09be\u09a8", "emoji": "\U0001FA65", "typical_hour": 6},
        {"id": "bath", "text": "\u0997\u09cb\u09b8\u09b2 \u0995\u09b0\u09c1\u09a8", "emoji": "\U0001F6BF", "typical_hour": 7},
        {"id": "breakfast", "text": "\u09a8\u09be\u09b6\u09cd\u09a4\u09be \u0995\u09b0\u09c1\u09a8", "emoji": "\U0001F373", "typical_hour": 8},
        {"id": "med1", "text": "\u09b8\u0995\u09be\u09b2\u09c7\u09b0 \u0993\u09b7\u09c1\u09a7 \u09a8\u09bf\u09a8", "emoji": "\U0001F48A", "typical_hour": 8},
        {"id": "walk", "text": "\u09b9\u09be\u099f\u09a4\u09c7 \u09af\u09be\u09a8", "emoji": "\U0001F6B6", "typical_hour": 9},
        {"id": "lunch", "text": "\u09ae\u09a7\u09cd\u09af\u09be\u09a8\u09cd\u09a8 \u0996\u09be\u09a8 \u0996\u09be\u09a8", "emoji": "\U0001F35A", "typical_hour": 12},
        {"id": "rest", "text": "\u09ac\u09bf\u09b6\u09cd\u09b0\u09be\u09ae", "emoji": "\U0001F4A4", "typical_hour": 14},
        {"id": "tea", "text": "\u09b8\u09a8\u09cd\u09a7\u09cd\u09af\u09be\u09b0 \u099a\u09be", "emoji": "\U0001FAD6", "typical_hour": 16},
        {"id": "prayer", "text": "\u09aa\u09cd\u09b0\u09be\u09b0\u09cd\u09a5\u09a8\u09be \u09ac\u09be \u09a7\u09cd\u09af\u09be\u09a8", "emoji": "\U0001F64F", "typical_hour": 18},
        {"id": "dinner", "text": "\u09b0\u09be\u09a4\u09c7\u09b0 \u0996\u09be\u09a8 \u0996\u09be\u09a8", "emoji": "\U0001F35B", "typical_hour": 19},
        {"id": "med2", "text": "\u09b0\u09be\u09a4\u09c7\u09b0 \u0993\u09b7\u09c1\u09a7 \u09a8\u09bf\u09a8", "emoji": "\U0001F48A", "typical_hour": 21},
        {"id": "sleep", "text": "\u0998\u09c1\u09ae\u09a4\u0947 \u09af\u09be\u09a8", "emoji": "\U0001F319", "typical_hour": 22},
    ],
    "as": [
        {"id": "wake", "text": "\u098f\u0995\u09c1\u09a8 \u0989\u09a0\u09a4", "emoji": "\U0001F305", "typical_hour": 6},
        {"id": "wash", "text": "\u09a6\u09be\u0981\u09a4 \u09ae\u09be\u099c\u09a4", "emoji": "\U0001FA65", "typical_hour": 6},
        {"id": "bath", "text": "\u0997\u09be\u09a7\u09c1\u0993\u09f1\u09be", "emoji": "\U0001F6BF", "typical_hour": 7},
        {"id": "breakfast", "text": "\u099c\u09b2\u09be\u0996\u09f1\u09be \u0996\u09be\u09f1\u09be", "emoji": "\U0001F373", "typical_hour": 8},
        {"id": "med1", "text": "\u09aa\u09c1\u09f0\u09c1\u09f1\u09bf\u09b0 \u0993\u09b7\u09c1\u09a7 \u09b2\u09f1\u09be", "emoji": "\U0001F48A", "typical_hour": 8},
        {"id": "walk", "text": "\u09ad\u09cd\u09f0\u09ae\u09a3\u09a4 \u09af\u09be\u09f1\u09be", "emoji": "\U0001F6B6", "typical_hour": 9},
        {"id": "lunch", "text": "\u09ae\u09a7\u09bf\u09f1\u09be\u09b9\u09cd\u09a8\u09c0\u09af\u09bc \u09ad\u09cb\u099c\u09a8", "emoji": "\U0001F35A", "typical_hour": 12},
        {"id": "rest", "text": "\u09ac\u09bf\u09b6\u09cd\u09f0\u09be\u09ae", "emoji": "\U0001F4A4", "typical_hour": 14},
        {"id": "tea", "text": "\u0997\u09a7\u09c1\u09b2\u09bf\u09af\u09bc\u09be \u099a\u09be", "emoji": "\U0001FAD6", "typical_hour": 16},
        {"id": "prayer", "text": "\u09aa\u09cd\u09f0\u09be\u09b0\u09cd\u09a5\u09a8\u09be \u09ac\u09be \u09a7\u09cd\u09af\u09be\u09a8", "emoji": "\U0001F64F", "typical_hour": 18},
        {"id": "dinner", "text": "\u09b0\u09be\u09a4\u09bf\u09f0 \u09ad\u09cb\u099c\u09a8", "emoji": "\U0001F35B", "typical_hour": 19},
        {"id": "med2", "text": "\u09b0\u09be\u09a4\u09bf\u09f0 \u0993\u09b7\u09c1\u09a7 \u09b2\u09f1\u09be", "emoji": "\U0001F48A", "typical_hour": 21},
        {"id": "sleep", "text": "\u09b6\u09c1\u0984\u09f1\u09be\u09a4 \u09af\u09be\u09f1\u09be", "emoji": "\U0001F319", "typical_hour": 22},
    ],
}

OBJECT_RECOGNITION_ITEMS = {
    "home": {
        "en": ["Cup", "Glasses", "Watch", "Key", "Book", "Comb", "Spoon", "Towel"],
        "hi": ["\u0915\u092a", "\u091a\u0937\u094d\u092e\u093e", "\u0918\u0921\u093c\u0940", "\u091a\u093e\u092c\u0940", "\u0915\u093f\u0924\u093e\u092c", "\u0915\u0902\u0918\u093e", "\u091a\u092e\u094d\u092e\u091a", "\u0924\u094c\u0932\u093f\u092f\u093e"],
        "bn": ["\u0995\u09be\u09aa", "\u099a\u09b7\u09ae\u09be", "\u0998\u09a1\u09bc\u09bf", "\u099a\u09be\u09ac\u09bf", "\u09ac\u0987", "\u099a\u09c1\u09b2\u09bf", "\u099a\u09be\u09ae\u099a", "\u0997\u09be\u09ae\u099b\u09be"],
        "as": ["\u0995\u09be\u09aa", "\u099a\u09a1\u09bc\u09c1\u0993\u09f1\u09be", "\u0998\u09a1\u09bc\u09bf", "\u099a\u09be\u09ac\u09bf", "\u0995\u09bf\u09a4\u09be\u09aa", "\u09ab\u09c1\u09f0\u09bf", "\u099a\u09be\u09ae\u099a", "\u0997\u09be\u09ae\u099b\u09be"],
    },
}

WORDS_FOR_MEMORY = {
    "en": ["apple", "river", "flower", "house", "sun", "moon", "tree", "bird", "fish", "boat"],
    "hi": ["\u0938\u0947\u092c", "\u0928\u0926\u0940", "\u092b\u0942\u0932", "\u0918\u0930", "\u0938\u0942\u0930\u091c", "\u091a\u093e\u0901\u0926", "\u092a\u0947\u0921\u093c", "\u092a\u0915\u094d\u0937\u0940", "\u092e\u091b\u0932\u0940", "\u0928\u093e\u0935"],
    "bn": ["\u0986\u09aa\u09c7\u09b2", "\u09a8\u09a6\u09c0", "\u09ab\u09c1\u09b2", "\u09ac\u09be\u09a1\u09bc\u09bf", "\u09b8\u09c2\u09b0\u09cd\u09af", "\u099a\u09be\u0981\u09a6", "\u0997\u09be\u099b", "\u09aa\u09be\u0996\u09c0", "\u09ae\u09be\u099b", "\u09a8\u09be\u0989\u0995\u09be"],
    "as": ["\u0986\u09aa\u09c1\u09b0", "\u09a8\u09a6\u09c0", "\u09ab\u09c1\u09b2", "\u0998\u09b0", "\u09ac\u09c7\u09b2\u09bf", "\u099c\u09a8\u09c0\u09b8", "\u0997\u09be\u099b", "\u099a\u09f0\u09c1", "\u09ae\u09be\u09b8", "\u09a8\u09be\u0989"],
}

NUMBER_SETS = {
    "en": ["3, 7, 1", "5, 2, 9", "8, 4, 6", "2, 9, 5, 1", "7, 3, 8, 4", "4, 1, 9, 6, 2", "8, 5, 3, 7, 1", "6, 2, 9, 4, 8"],
    "hi": ["\u0963, \u0969, \u0967", "\u096b, \u0968, \u096f", "\u096e, \u096a, \u096c", "\u0968, \u096f, \u096b, \u0967", "\u0969, \u0969, \u096e, \u096a", "\u096a, \u0967, \u096f, \u096c, \u0968", "\u096e, \u096b, \u0969, \u0969, \u0967", "\u096c, \u0968, \u096f, \u096a, \u096e"],
    "bn": ["\u09e9, \u09ef, \u09e7", "\u09eb, \u09e8, \u09ef", "\u09ee, \u09ea, \u09ec", "\u09e8, \u09ef, \u09eb, \u09e7", "\u09ef, \u09ef, \u09ee, \u09ea", "\u09ea, \u09e7, \u09ef, \u09ec, \u09e8", "\u09ee, \u09eb, \u09ef, \u09ef, \u09e7", "\u09ec, \u09e8, \u09ef, \u09ea, \u09ee"],
    "as": ["\u09e9, \u09ef, \u09e7", "\u09eb, \u09e8, \u09ef", "\u09ee, \u09ea, \u09ec", "\u09e8, \u09ef, \u09eb, \u09e7", "\u09ef, \u09ef, \u09ee, \u09ea", "\u09ea, \u09e7, \u09ef, \u09ec, \u09e8", "\u09ee, \u09eb, \u09ef, \u09ef, \u09e7", "\u09ec, \u09e8, \u09ef, \u09ea, \u09ee"],
}

FACE_EMOJIS = ["\U0001F468", "\U0001F469", "\U0001F474", "\U0001F475", "\U0001F9D3", "\U0001F471", "\U0001F466", "\U0001F467"]
FACE_NAMES = {
    "en": ["Grandpa", "Grandma", "Uncle", "Aunty", "Elder", "Friend", "Boy", "Girl"],
    "hi": ["\u0926\u093e\u0926\u093e", "\u0926\u093e\u0926\u0940", "\u091a\u093e\u091a\u093e", "\u0924\u093e\u0907", "\u092c\u0941\u091c\u093c\u0947\u0930\u094d\u0917", "\u0926\u094b\u0938\u094d\u0924", "\u0932\u0921\u0915\u093e", "\u0932\u0921\u0915\u0940"],
    "bn": ["\u09a6\u09be\u09a6\u09be", "\u09a6\u09be\u09a6\u09bf", "\u0995\u09be\u0995\u09be", "\u09a4\u09be\u09a4\u09bf", "\u09ac\u09c1\u099c\u09c1\u09b0\u09cd\u0997", "\u09ac\u09a8\u09cd\u09a7\u09c1", "\u099b\u09c7\u09b2\u09be", "\u099b\u09c7\u09b2\u09bf"],
    "as": ["\u09a6\u09be\u09a6\u09be", "\u09a6\u09be\u09a6\u09bf", "\u0995\u09be\u0995\u09be", "\u09a4\u09be\u09a4\u09bf", "\u09ac\u09c1\u099c\u09c1\u09b0\u09cd\u0997", "\u09ac\u09a8\u09cd\u09a7\u09c1", "\u099b\u09c7\u09b2\u09be", "\u099b\u09c7\u09b2\u09bf"],
}

SHOPPING_ITEMS = {
    "en": ["Rice", "Milk", "Eggs", "Banana", "Bread", "Tea", "Sugar", "Fish", "Apple", "Onion"],
    "hi": ["\u091a\u093e\u0935\u0932", "\u0926\u0942\u0927", "\u0905\u0902\u0921\u0947", "\u0915\u0947\u0932\u093e", "\u0930\u094b\u091f\u0940", "\u091a\u093e\u092f", "\u091a\u0940\u0928\u0940", "\u092e\u093e\u091d", "\u0938\u0947\u092c", "\u092a\u094d\u092f\u093e\u091c"],
    "bn": ["\u099a\u09be\u09b2", "\u09a6\u09c1\u09a7", "\u099f\u09c7\u09b2\u09be", "\u0995\u09b2\u09be", "\u09b0\u09c1\u099f\u09bf", "\u099a\u09be", "\u099a\u09bf\u09a8\u09bf", "\u09ae\u09be\u099b", "\u0986\u09aa\u09c7\u09b2", "\u09aa\u09bf\u09af\u09bc\u09be\u099c"],
    "as": ["\u09ad\u09be\u09a4", "\u0997\u09be\u0993\u09b0", "\u099f\u09c7\u09b2\u09be", "\u0995\u09b2\u09be", "\u09b0\u09c1\u099f\u09bf", "\u099a\u09be\u09b9", "\u099a\u09bf\u09a8\u09bf", "\u09ae\u09be\u099b", "\u0986\u09aa\u09c1\u09b0", "\u09aa\u09bf\u09af\u09bc\u09be\u099c"],
}

EMOTION_FACES = ["\U0001F600", "\U0001F622", "\U0001F621", "\U0001F60E", "\U0001F62B", "\U0001F604", "\U0001F62E", "\U0001F625"]
EMOTION_LABELS = {
    "en": ["Happy", "Crying", "Angry", "Cool", "Tired", "Laughing", "Surprised", "Worried"],
    "hi": ["\u0916\u0941\u0936", "\u0930\u094b\u092f\u093e", "\u0917\u0941\u0938\u094d\u0938\u093e", "\u0936\u093e\u0928\u094d\u0926\u093e\u0930", "\u0925\u0915\u093e", "\u0939\u0938 \u0930\u0939\u093e", "\u0939\u0948\u0930\u093e\u0928", "\u091a\u093f\u0902\u0924\u093f\u0924"],
    "bn": ["\u09b6\u09a8\u09cd\u09a6\u09be", "\u0995\u09be\u09a8\u09cd\u09a1\u09be", "\u09b0\u09be\u0997", "\u09b6\u09be\u09a8\u09cd\u09a6\u09be\u09b0", "\u09a5\u0995", "\u09b9\u09be\u09b8 \u09b0\u09c7\u099b\u09c7", "\u09b9\u09cd\u09af\u09be\u09b0\u09be\u0993", "\u099a\u09bf\u09a8\u09cd\u09a4\u09be"],
    "as": ["\u09b6\u09a8\u09cd\u09a6\u09be", "\u0995\u09be\u09a8\u09cd\u09a1\u09be", "\u09b0\u09be\u0997", "\u09b6\u09be\u09a8\u09cd\u09a6\u09be\u09b0", "\u09a5\u0995", "\u09b9\u09be\u09b8 \u09b0\u09c7\u099b\u09c7", "\u09b9\u09cd\u09af\u09be\u09b0\u09be\u0993", "\u099a\u09bf\u09a8\u09cd\u09a4\u09be"],
}

WORD_PAIRS = {
    "en": [
        ("Sun", "Light"), ("Moon", "Night"), ("Rain", "Water"), ("Fire", "Hot"),
        ("Fish", "Swim"), ("Bird", "Fly"), ("Dog", "Bark"), ("Cat", "Meow"),
        ("Door", "Open"), ("Clock", "Time"),
    ],
    "hi": [
        ("\u0938\u0942\u0930\u091c", "\u0930\u094b\u0936\u0928\u0940"), ("\u091a\u093e\u0901\u0926", "\u0930\u093e\u0924"), ("\u092c\u093e\u0930\u093f\u0936", "\u092a\u093e\u0928\u0940"), ("\u0906\u0917", "\u0917\u0930\u094d\u092e"),
        ("\u092e\u093e\u091d", "\u0924\u0948\u0930"), ("\u092a\u0915\u094d\u0937\u0940", "\u0909\u0921\u093c"), ("\u0915\u0941\u0915\u094d\u0921\u093c", "\u092d\u094c\u0915\u0928\u093e"), ("\u092c\u093f\u0932\u093e\u090f", "\u092e\u094d\u092f\u093e\u0901"),
        ("\u0926\u0935\u093e\u091c\u093c\u093e", "\u0916\u094b\u0932\u0928\u093e"), ("\u0918\u0921\u093c\u0940", "\u0938\u092e\u092f"),
    ],
    "bn": [
        ("\u09b8\u09c2\u09b0\u09cd\u09af", "\u099c\u09cd\u09b2\u09be\u09a8\u09bf"), ("\u099a\u09be\u0981\u09a6", "\u09b0\u09be\u09a4\u09cd\u09b0\u09bf"), ("\u09ac\u09c3\u09b7\u09cd\u099f\u09bf", "\u09aa\u09be\u09a8\u09bf"), ("\u0996\u09be", "\u0997\u09b0\u09ae"),
        ("\u09ae\u09be\u099b", "\u09ad\u09be\u09b8\u09be"), ("\u09aa\u09be\u0996\u09c0", "\u0989\u09a1\u09bc\u09be"), ("\u0995\u09c1\u0995\u09c1\u09b0", "\u0996\u09c1\u0981\u0995\u09c1\u09b0"), ("\u09ac\u09bf\u09b2\u09be\u09aa\u09bf", "\u0996\u09c1\u09b2\u09be"),
        ("\u09a6\u09c7\u09ac\u09be\u09b2\u09be", "\u0996\u09c1\u09b2\u09be"), ("\u0998\u09a1\u09bc\u09bf", "\u09b8\u09ae\u09af\u09bc"),
    ],
    "as": [
        ("\u09b8\u09c2\u09b0\u09cd\u09af", "\u099c\u09cd\u09b2\u09be\u09a8\u09bf"), ("\u099a\u09be\u0981\u09a6", "\u09b0\u09be\u09a4\u09cd\u09b0\u09bf"), ("\u09ac\u09c3\u09b7\u09cd\u099f\u09bf", "\u09aa\u09be\u09a8\u09bf"), ("\u0996\u09be", "\u0997\u09b0\u09ae"),
        ("\u09ae\u09be\u099b", "\u09ad\u09be\u09b8\u09be"), ("\u09aa\u09be\u0996\u09c0", "\u0989\u09a1\u09bc\u09be"), ("\u0995\u09c1\u0995\u09c1\u09b0", "\u0996\u09c1\u0981\u0995\u09c1\u09b0"), ("\u09ac\u09bf\u09b2\u09be\u09aa\u09bf", "\u0996\u09c1\u09b2\u09be"),
        ("\u09a6\u09c7\u09ac\u09be\u09b2\u09be", "\u0996\u09c1\u09b2\u09be"), ("\u0998\u09a1\u09bc\u09bf", "\u09b8\u09ae\u09af\u09bc"),
    ],
}


class AdaptiveDifficultyEngine:
    def __init__(self, patient_id: str, game_type: str):
        self.patient_id = patient_id
        self.game_type = game_type

    def compute_next_level(self, accuracy_pct: float, current_level: float) -> float:
        if accuracy_pct >= 90:
            return min(5.0, current_level + 0.5)
        if accuracy_pct >= 75:
            return max(1.0, current_level + 0.2)
        if accuracy_pct >= 55:
            return max(1.0, current_level - 0.1)
        return max(1.0, current_level - 0.5)

    def difficulty_params(self, level: float) -> dict[str, Any]:
        params = {
            "grid_size": 4 if level < 2 else 4 if level < 3 else 6,
            "pairs": 4 if level < 2 else 6 if level < 3 else 8,
            "sequence_length": 3 if level < 2 else 4 if level < 3 else 6,
            "time_seconds": max(30, 60 - int((level - 1) * 5)),
            "options_count": 4 if level < 3 else 6,
            "items_to_recall": 3 if level < 2 else 4 if level < 3 else 5,
            "distractors": 2 if level < 3 else 3,
        }
        return params


class MemoryGame:
    def __init__(self, language: str = "en", theme: str = "flowers", level: float = 1.0):
        self.language = language if language in ("en", "hi", "bn", "as") else "en"
        self.theme = theme if theme in NER_EMOJI else "flowers"
        self.level = level
        self.params = AdaptiveDifficultyEngine("", "").difficulty_params(level)

    def generate_puzzle(self) -> dict[str, Any]:
        num_pairs = self.params["pairs"]
        emojis = NER_EMOJI[self.theme]
        names = NER_THEME_NAMES[self.theme]
        lang_names = names.get(self.language, names["en"])
        selected = random.sample(range(len(emojis)), min(num_pairs, len(emojis)))
        cards = []
        for ci in selected:
            card = {"id": f"c{ci}", "emoji": emojis[ci], "name": lang_names[ci]}
            cards.append(card)
            cards.append(dict(card))
        random.shuffle(cards)
        return {
            "game": "memory_match",
            "title": "Memory Match",
            "cards": cards,
            "num_pairs": num_pairs,
            "theme": self.theme,
            "language": self.language,
            "level": self.level,
            "time_seconds": self.params["time_seconds"],
        }


class SequenceMemoryGame:
    def __init__(self, language: str = "en", level: float = 1.0):
        self.language = language if language in ("en", "hi", "bn", "as") else "en"
        self.level = level
        self.params = AdaptiveDifficultyEngine("", "").difficulty_params(level)
        self.all_words = WORDS_FOR_MEMORY.get(self.language, WORDS_FOR_MEMORY["en"])

    def generate_puzzle(self) -> dict[str, Any]:
        seq_length = self.params["sequence_length"]
        sequence = random.sample(self.all_words, seq_length)
        distractors = [w for w in self.all_words if w not in sequence]
        options = sequence + random.sample(distractors, min(self.params["distractors"], len(distractors)))
        random.shuffle(options)
        return {
            "game": "sequence_memory",
            "title": "Word Memory",
            "sequence": sequence,
            "options": options,
            "sequence_length": seq_length,
            "language": self.language,
            "level": self.level,
        }


class PatternRecognitionGame:
    def __init__(self, language: str = "en", level: float = 1.0):
        self.language = language if language in ("en", "hi", "bn", "as") else "en"
        self.level = level
        self.params = AdaptiveDifficultyEngine("", "").difficulty_params(level)

    def generate_puzzle(self) -> dict[str, Any]:
        emoji_set = NER_EMOJI["nature"] + NER_EMOJI["flowers"]
        pattern_len = 3 if self.level < 2 else 4 if self.level < 3.5 else 5
        pattern = []
        last = None
        for i in range(pattern_len):
            choices = [e for e in emoji_set if e != last]
            e = random.choice(choices)
            pattern.append(e)
            last = e
        next_candidates = [e for e in emoji_set if e != pattern[-1]]
        correct = random.choice(next_candidates)
        options = [correct]
        for e in random.sample(emoji_set, self.params["options_count"] - 1):
            if e not in options and e != pattern[-1]:
                options.append(e)
        random.shuffle(options)
        return {
            "game": "pattern_recognition",
            "title": "Pattern Recognition",
            "pattern": pattern,
            "options": options,
            "correct_answer": correct,
            "language": self.language,
            "level": self.level,
        }


class DailyRoutineGame:
    def __init__(self, language: str = "en", level: float = 1.0):
        self.language = language if language in ("en", "hi", "bn", "as") else "en"
        self.level = level
        activities = DAILY_ROUTINE_ACTIVITIES.get(self.language, DAILY_ROUTINE_ACTIVITIES["en"])
        count = 4 if level < 2 else 5 if level < 3 else 7
        self.activities = random.sample(activities, min(count, len(activities)))
        for i, act in enumerate(self.activities):
            act["position"] = i

    def generate_puzzle(self) -> dict[str, Any]:
        shuffled = random.sample(self.activities, len(self.activities))
        return {
            "game": "daily_routine",
            "title": "Daily Routine",
            "activities": shuffled,
            "correct_order": [a["id"] for a in self.activities],
            "language": self.language,
            "level": self.level,
        }


class ObjectRecognitionGame:
    def __init__(self, language: str = "en", level: float = 1.0):
        self.language = language if language in ("en", "hi", "bn", "as") else "en"
        self.level = level
        self.params = AdaptiveDifficultyEngine("", "").difficulty_params(level)
        items = OBJECT_RECOGNITION_ITEMS["home"]
        self.items = items.get(self.language, items["en"])

    def generate_puzzle(self) -> dict[str, Any]:
        num_options = self.params["options_count"]
        answer_index = random.randrange(num_options)
        options = random.sample(self.items, min(num_options, len(self.items)))
        display = []
        for i, item in enumerate(options):
            display.append({"index": i, "label": item, "is_answer": i == answer_index})
        random.shuffle(display)
        shuffled_answer = next((d["index"] for d in display if d["is_answer"]), 0)
        return {
            "game": "object_recognition",
            "title": "Object Recognition",
            "question": "Find the special object",
            "objects": display,
            "answer_option": shuffled_answer,
            "language": self.language,
            "level": self.level,
        }


class ColorSortGame:
    def __init__(self, language: str = "en", level: float = 1.0):
        self.language = language if language in ("en", "hi", "bn", "as") else "en"
        self.level = level
        self.colors = [
            {"name": "red", "hex": "#ef4444", "hi": "\u0932\u093e\u0932", "bn": "\u09b2\u09be\u09b2", "as": "\u09b0\u09be\u0997\u09be"},
            {"name": "green", "hex": "#22c55e", "hi": "\u0939\u0930\u093e", "bn": "\u09b8\u09ac\u09c1\u099c", "as": "\u09b8\u09c7\u0987\u099c\u09c0"},
            {"name": "blue", "hex": "#3b82f6", "hi": "\u0928\u0940\u0932\u093e", "bn": "\u09a8\u09c0\u09b2", "as": "\u09a8\u09c0\u09b2\u09be"},
            {"name": "yellow", "hex": "#eab308", "hi": "\u092a\u0940\u0932\u093e", "bn": "\u09b9\u09b2\u09c1\u09a6", "as": "\u09b9\u09b2\u09a4\u09bf\u09af\u09bc\u09be"},
            {"name": "orange", "hex": "#f97316", "hi": "\u0928\u093e\u0930\u0902\u0917\u0940", "bn": "\u0995\u09ae\u09b2\u09be", "as": "\u0995\u09ae\u09b2\u09be"},
            {"name": "purple", "hex": "#a855f7", "hi": "\u092c\u0948\u0902\u0917\u0928\u0940", "bn": "\u09ac\u09c7\u0997\u09c1\u09a8\u09bf", "as": "\u09ac\u09c7\u0997\u09c1\u09a8\u09c0"},
        ]

    def generate_puzzle(self) -> dict[str, Any]:
        target = random.choice(self.colors)
        label = target.get(self.language, target.get("en", target["name"]))
        num_options = 4 if self.level < 3 else 6
        shuffled = random.sample(self.colors, min(num_options, len(self.colors)))
        display = []
        correct_id = None
        for c in shuffled:
            entry = {"hex": c["hex"], "name": c.get(self.language, c["name"]), "lang_name": c["name"]}
            if c["name"] == target["name"]:
                correct_id = c["name"]
            display.append(entry)
        return {
            "game": "color_sort",
            "title": "Color Match",
            "target_label": label,
            "colors": display,
            "correct_answer": correct_id,
            "language": self.language,
            "level": self.level,
        }


class NumberSequenceGame:
    def __init__(self, language: str = "en", level: float = 1.0):
        self.language = language if language in ("en", "hi", "bn", "as") else "en"
        self.level = level

    def generate_puzzle(self) -> dict[str, Any]:
        sets = NUMBER_SETS.get(self.language, NUMBER_SETS["en"])
        count = 2 if self.level < 2 else 3 if self.level < 3.5 else 4
        available = [s for s in sets if len(s.split(",")) <= count + 1]
        if not available:
            available = sets
        chosen = random.choice(available)
        nums = [n.strip() for n in chosen.split(",")]
        target = random.choice(nums)
        options = random.sample(nums, min(count, len(nums)))
        if target not in options:
            options[-1] = target
        random.shuffle(options)
        return {
            "game": "number_sequence",
            "title": "Number Sequence",
            "sequence": nums,
            "target": target,
            "options": options,
            "language": self.language,
            "level": self.level,
        }


class FaceNameGame:
    def __init__(self, language: str = "en", level: float = 1.0):
        self.language = language if language in ("en", "hi", "bn", "as") else "en"
        self.level = level

    def generate_puzzle(self) -> dict[str, Any]:
        count = 3 if self.level < 2.5 else 4
        names = FACE_NAMES.get(self.language, FACE_NAMES["en"])
        indices = random.sample(range(len(FACE_EMOJIS)), count)
        pairs = [(FACE_EMOJIS[i], names[i]) for i in indices]
        target = random.choice(pairs)
        options = random.sample(names, min(count, len(names)))
        if target[1] not in options:
            options[-1] = target[1]
        random.shuffle(options)
        return {
            "game": "face_name_match",
            "title": "Face-Name Match",
            "face": target[0],
            "correct_name": target[1],
            "options": options,
            "all_pairs": [{"emoji": e, "name": n} for e, n in pairs],
            "language": self.language,
            "level": self.level,
        }


class ShoppingListGame:
    def __init__(self, language: str = "en", level: float = 1.0):
        self.language = language if language in ("en", "hi", "bn", "as") else "en"
        self.level = level

    def generate_puzzle(self) -> dict[str, Any]:
        items = SHOPPING_ITEMS.get(self.language, SHOPPING_ITEMS["en"])
        count = 3 if self.level < 2 else 4 if self.level < 3.5 else 5
        chosen = random.sample(items, count)
        options_pool = [i for i in items if i not in chosen]
        distractors = random.sample(options_pool, min(count, len(options_pool)))
        all_options = chosen + distractors
        random.shuffle(all_options)
        return {
            "game": "shopping_list",
            "title": "Shopping List",
            "list_items": chosen,
            "options": all_options,
            "count": count,
            "language": self.language,
            "level": self.level,
        }


class ClockReadingGame:
    def __init__(self, language: str = "en", level: float = 1.0):
        self.language = language if language in ("en", "hi", "bn", "as") else "en"
        self.level = level

    def generate_puzzle(self) -> dict[str, Any]:
        if self.level < 2:
            hour = random.choice([3, 6, 9, 12])
            minute = 0
        elif self.level < 3.5:
            hour = random.randint(1, 12)
            minute = random.choice([0, 15, 30, 45])
        else:
            hour = random.randint(1, 12)
            minute = random.choice([5, 10, 20, 25, 35, 40, 50, 55])
        target_time = f"{hour}:{minute:02d}"
        options = [target_time]
        while len(options) < 4:
            rh = random.randint(1, 12)
            rm = random.choice([0, 15, 30, 45]) if self.level < 3.5 else random.choice([0, 10, 20, 30, 40, 50])
            t = f"{rh}:{rm:02d}"
            if t not in options:
                options.append(t)
        random.shuffle(options)
        return {
            "game": "clock_reading",
            "title": "Clock Reading",
            "hour": hour,
            "minute": minute,
            "target_time": target_time,
            "options": options,
            "language": self.language,
            "level": self.level,
        }


class EmotionRecognitionGame:
    def __init__(self, language: str = "en", level: float = 1.0):
        self.language = language if language in ("en", "hi", "bn", "as") else "en"
        self.level = level

    def generate_puzzle(self) -> dict[str, Any]:
        count = 4 if self.level < 3 else 5
        labels = EMOTION_LABELS.get(self.language, EMOTION_LABELS["en"])
        idx = random.randrange(len(EMOTION_FACES))
        face = EMOTION_FACES[idx]
        correct = labels[idx]
        options = random.sample(labels, min(count, len(labels)))
        if correct not in options:
            options[-1] = correct
        random.shuffle(options)
        return {
            "game": "emotion_recognition",
            "title": "Emotion Recognition",
            "face": face,
            "correct_emotion": correct,
            "options": options,
            "language": self.language,
            "level": self.level,
        }


class WordAssociationGame:
    def __init__(self, language: str = "en", level: float = 1.0):
        self.language = language if language in ("en", "hi", "bn", "as") else "en"
        self.level = level

    def generate_puzzle(self) -> dict[str, Any]:
        pairs = WORD_PAIRS.get(self.language, WORD_PAIRS["en"])
        count = 3 if self.level < 2.5 else 4
        chosen = random.sample(pairs, min(count, len(pairs)))
        first_words = [p[0] for p in chosen]
        second_words = [p[1] for p in chosen]
        distractors = [p[1] for p in pairs if p not in chosen]
        extra = random.sample(distractors, min(2, len(distractors))) if distractors else []
        all_second = second_words + extra
        random.shuffle(all_second)
        return {
            "game": "word_association",
            "title": "Word Association",
            "pairs": [{"first": p[0], "second": p[1]} for p in chosen],
            "first_words": first_words,
            "second_words": all_second,
            "correct_pairs": {p[0]: p[1] for p in chosen},
            "language": self.language,
            "level": self.level,
        }


class CognitiveGameEngine:
    def __init__(self):
        self.games = {
            "memory_match": {"title": "Memory Match", "desc": "Flip and match pairs of pictures", "category": "memory"},
            "sequence_memory": {"title": "Word Memory", "desc": "Remember the words in order", "category": "recall"},
            "pattern_recognition": {"title": "Pattern Recognition", "desc": "Find what comes next in the pattern", "category": "attention"},
            "daily_routine": {"title": "Daily Routine", "desc": "Put the daily activities in order", "category": "recall"},
            "object_recognition": {"title": "Object Recognition", "desc": "Find the special object", "category": "recognition"},
            "color_sort": {"title": "Color Match", "desc": "Tap the color that matches", "category": "attention"},
            "number_sequence": {"title": "Number Sequence", "desc": "Remember and repeat numbers", "category": "memory"},
            "face_name_match": {"title": "Face-Name Match", "desc": "Match faces with their names", "category": "recognition"},
            "shopping_list": {"title": "Shopping List", "desc": "Remember items on the list", "category": "memory"},
            "clock_reading": {"title": "Clock Reading", "desc": "Read the time on the clock", "category": "attention"},
            "emotion_recognition": {"title": "Emotion Recognition", "desc": "Identify the emotion shown", "category": "recognition"},
            "word_association": {"title": "Word Association", "desc": "Match words that go together", "category": "recall"},
        }

    def list_games(self) -> list[dict[str, Any]]:
        return [
            {"id": gid, **spec}
            for gid, spec in self.games.items()
        ]

    def new_game(self, game_type: str, language: str = "en", level: float = 1.0, seed: int | None = None) -> dict[str, Any]:
        if seed is not None:
            random.seed(seed + int(time.time() * 0) + int(game_type.__hash__() % (2**63)))
        dispatch = {
            "memory_match": lambda: MemoryGame(language=language, level=level).generate_puzzle(),
            "sequence_memory": lambda: SequenceMemoryGame(language=language, level=level).generate_puzzle(),
            "pattern_recognition": lambda: PatternRecognitionGame(language=language, level=level).generate_puzzle(),
            "daily_routine": lambda: DailyRoutineGame(language=language, level=level).generate_puzzle(),
            "object_recognition": lambda: ObjectRecognitionGame(language=language, level=level).generate_puzzle(),
            "color_sort": lambda: ColorSortGame(language=language, level=level).generate_puzzle(),
            "number_sequence": lambda: NumberSequenceGame(language=language, level=level).generate_puzzle(),
            "face_name_match": lambda: FaceNameGame(language=language, level=level).generate_puzzle(),
            "shopping_list": lambda: ShoppingListGame(language=language, level=level).generate_puzzle(),
            "clock_reading": lambda: ClockReadingGame(language=language, level=level).generate_puzzle(),
            "emotion_recognition": lambda: EmotionRecognitionGame(language=language, level=level).generate_puzzle(),
            "word_association": lambda: WordAssociationGame(language=language, level=level).generate_puzzle(),
        }
        if game_type not in dispatch:
            raise ValueError(f"Unknown game type: {game_type}")
        return dispatch[game_type]()

    def next_level(self, game_type: str, current_level: float, accuracy_pct: float) -> float:
        engine = AdaptiveDifficultyEngine("", game_type)
        return engine.compute_next_level(accuracy_pct, current_level)


def default_assessment() -> dict[str, Any]:
    return {
        "overall_score": 0,
        "memory_score": 0,
        "attention_score": 0,
        "recognition_score": 0,
        "recall_score": 0,
        "engagement_minutes": 0,
        "sessions_played": 0,
        "trend": "stable",
    }