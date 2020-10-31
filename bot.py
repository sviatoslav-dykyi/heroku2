# -*- coding: utf-8 -*-

import telebot
import config
import random
import retailcrm
import requests
import json
import websocket
import asyncio
import websockets
import logging
import socket
import argparse
import threading
import sys
from threading import Thread
try:
    import thread
except ImportError:
    import _thread as thread
import time

from telebot import types
from websocket import create_connection
from ws4py.client.threadedclient import WebSocketClient
logging.basicConfig(level=logging.INFO)

headers = {
    'X-Bot-Token': config.X_BOT_TOKEN
}

def pp_json(json_thing, sort=True, indents=4):
    if type(json_thing) is str:
        print(json.dumps(json.loads(
            json_thing), sort_keys=sort, indent=indents))
    else:
        print(json.dumps(json_thing,
                         sort_keys=sort, indent=indents))
    return None 

def orders_check(data, totalPageCount=7):    
    for x in range(1, int(totalPageCount)):
        result = requests.get(config.RETAIL_CRM_HOST + "/api/v5/orders?limit=100&page=" + str(
            x) + "&apiKey=" + config.RETAIL_CRM_API_KEY)
        html = result.json()                                    
        for key in html:
            if key == 'orders':
                for v in html[key]:
                    if data['message']['content'] == v['number']:
                        result = requests.get(config.RETAIL_CRM_HOST + "/api/v5/orders/" + str(
                            v['externalId']) + "?apiKey=" + config.RETAIL_CRM_API_KEY) 
                        html = result.json()
                        pp_json(html)
                        chat_template = html['order']['customFields']['chat_template']                            

                        if html['order']['delivery']['code'] == "self-delivery":
                            final = config.PAYMENT_DETAILS_v2
                        else:
                            final = config.PAYMENT_DETAILS_v1                            
                        
                        data = {
                            "chat_id": data['message']['chat_id'],
                            "scope": "public",
                            "type": "text",
                            "content": str(chat_template) + "\n\n" + str(final)  
                        }

                        url = "https://mg-s1.retailcrm.pro/api/bot/v1/messages"
                        requests.post(url, json=data, headers=headers) 
                        return False
            else:
                continue
    # answer = "к сожалению бот не смог распознать номер заказа, ожидайте подключения оператора"            
    # data = {
    #     "chat_id": data['message']['chat_id'],
    #     "scope": "public",
    #     "type": "text",
    #     "content": answer  
    # }

    # url = "https://mg-s1.retailcrm.pro/api/bot/v1/messages"
    # requests.post(url, json=data, headers=headers) 

async def switch_off(websocket):
    global consumer_handler     
    async for message in websocket:
        try:
            event = json.loads(message)  
            data = event['data']        
            if 'from' in data['message']:    
                from_type = data['message']['from']['type']            
                if event['type'] == 'message_new' and from_type != 'bot' and from_type != 'user': 
                    data = {
                        "chat_id": data['message']['chat_id'],
                        "scope": "public",
                        "type": "text",
                        "content": "Извините, сервис временно недоступен"    
                    }

                    url = "https://mg-s1.retailcrm.pro/api/bot/v1/messages"
                    requests.post(url, json=data, headers=headers) 

                elif event['type'] == 'message_new' and from_type == 'user': 
                    if 'content' in data['message']:
                        if data['message']['content'] == '/turnmeon':                    
                            consumer_handler = consumer_handler_on
        except Exception as e:
            print(e)                     

async def switch_on(websocket):    
    global consumer_handler
    print('Switch ON')    
    async for message in websocket:        
        try:            
            event = json.loads(message)  
            data = event['data']
            if 'from' in data['message']:          
                from_type = data['message']['from']['type'] 
                if event['type'] == 'message_new' and from_type != 'bot' and from_type != 'user':   
                    if 'content' in data['message']:
                        if data['message']['content'] == '/start':
                            data = {
                                "chat_id": data['message']['chat_id'],
                                "scope": "public",
                                "type": "text",
                                "content": config.START_TEMPLATE    
                            }

                            url = "https://mg-s1.retailcrm.pro/api/bot/v1/messages"
                            requests.post(url, json=data, headers=headers)
                        else:    
                            result = requests.get(config.RETAIL_CRM_HOST + "/api/v5/orders?limit=100&apiKey=" + config.RETAIL_CRM_API_KEY)        
                            html = result.json()        

                            totalPageCount = html['pagination']['totalPageCount']
                            print(totalPageCount)
                            orders_check(data)                           
                elif event['type'] == 'message_new' and from_type == 'user': 
                    if 'content' in data['message']:                    
                        if data['message']['content'] == '/turnmeoff':
                            consumer_handler = consumer_handler_off                         
                            print('Turned off')
        except Exception as e:
            print(e)                          
                        
async def consumer_handler_off(websocket):
    print('consumer_handler_off')
    await switch_off(websocket) 

async def consumer_handler_on(websocket):
    print('consumer_handler_on')
    await switch_on(websocket) 

async def consumer_handler(websocket):
    await switch_on(websocket)           



logger = logging.getLogger(__name__)

logging.basicConfig(
    stream=sys.stdout,
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class WSClient():
    def __init__(self, url, **kwargs):
        self.url = url
        # set some default values
        self.extra_headers = kwargs.get('extra_headers') or {}
        self.reply_timeout = kwargs.get('reply_timeout') or 10
        self.ping_timeout = kwargs.get('ping_timeout') or 5
        self.sleep_time = kwargs.get('sleep_time') or 5
        self.callback = kwargs.get('callback')


    async def listen_forever(self):
        while True:
        # outer loop restarted every time the connection fails            
            logger.debug('Creating new connection...')
            try:
                async with websockets.connect(self.url, extra_headers=self.extra_headers) as ws:
                    while True:
                    # listener loop
                        try:
                            print(111)                            
                            reply = await asyncio.wait_for(consumer_handler(ws), timeout=self.reply_timeout)                            
                        except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed):
                            try:
                                print(222)
                                pong = await ws.ping()
                                await asyncio.wait_for(pong, timeout=self.ping_timeout)
                                logger.debug('Ping OK, keeping connection alive...')
                                continue
                            except:
                                logger.debug(
                                    'Ping error - retrying connection in {} sec (Ctrl-C to quit)'.format(self.sleep_time))
                                await asyncio.sleep(self.sleep_time)
                                break
                        logger.debug('Server said > {}'.format(reply))                        
            except socket.gaierror:
                logger.debug(
                    'Socket error - retrying connection in {} sec (Ctrl-C to quit)'.format(self.sleep_time))
                await asyncio.sleep(self.sleep_time)
                continue
            except ConnectionRefusedError:
                logger.debug('Nobody seems to listen to this endpoint. Please check the URL.')
                logger.debug('Retrying connection in {} sec (Ctrl-C to quit)'.format(self.sleep_time))
                await asyncio.sleep(self.sleep_time)
                continue


def start_ws_client(client):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(client.listen_forever())

if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('--url',
                        required=False,
                        # set here your URL
                        default='wss://mg-s1.retailcrm.pro/api/bot/v1/ws?events=message_new,message_updated',
                        dest='url',
                        help='Websocket URL')

    parser.add_argument('--extra_headers',
                        required=False,                        
                        default={'X-Bot-Token': config.X_BOT_TOKEN},
                        type=dict,
                        dest='extra_headers',
                        help='Websocket extra_headers')

    parser.add_argument('--reply-timeout',
                        required=False,
                        dest='reply_timeout',
                        type=int,
                        help='Timeout for reply from server')

    parser.add_argument('--ping-timeout',
                        required=False,
                        dest='ping_timeout',
                        default=None,
                        help='Timeout when pinging the server')

    parser.add_argument('--sleep',
                        required=False,
                        type=int,
                        dest='sleep_time',
                        default=None,
                        help='Sleep time before retrieving connection')

    args = parser.parse_args()    

    ws_client = WSClient(**vars(args))
    start_ws_client(ws_client)



