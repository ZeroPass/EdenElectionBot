import asyncio
import os
from datetime import datetime, timedelta
from enum import Enum

from pyrogram.errors import FloodWait
from pyrogram.handlers import MessageHandler
from pyrogram.types import Chat, InlineKeyboardMarkup, ChatPrivileges, InlineKeyboardButton, BotCommand

from app.constants.parameters import *
from app.database import Database
from app.database.participant import Participant
from app.dateTimeManagement import DateTimeManagement
from app.log.log import Log

from multiprocessing import Process

from pyrogram import Client, emoji, filters, types, idle

import time

from app.text.textManagement import GroupCommunicationTextManagement, Button, BotCommunicationManagement, \
    WellcomeMessageTextManagement


# api_id = 48490
# api_hash = "507315c8796f15903299b47730838c77"

# , /*bot_token="5512475717:AAGp0a451eha7X00wVJ4csCC0Mh_U1J1nxk"
# async def main():
#    async with Client("bot1", api_id, api_hash) as app:
#        await app.send_message("me", "Greetings from **Pyrogram**!")

class SessionType(Enum):
    USER = 1
    BOT = 2


class CommunicationException(Exception):
    pass


LOG = Log(className="Communication")


class Communication:
    # sessions = {}
    sessionUser: Client = None
    sessionBot: Client = None
    isInitialized: bool = False

    def __init__(self):
        LOG.info("Init communication")

    def start(self, apiId: int, apiHash: str, botToken: str):
        assert isinstance(apiId, int), "ApiId should be int"
        assert isinstance(apiHash, str), "ApiHash should be str"
        assert isinstance(botToken, str), "BotToken should be str"
        LOG.debug("Starting communication sessions..")
        try:
            LOG.debug("... user session")
            self.setSession(sessionType=SessionType.USER,
                            client=Client(name=communication_session_name_user,
                                          api_id=apiId,
                                          api_hash=apiHash))
            self.startSession(sessionType=SessionType.USER)

            LOG.debug("... bot session")
            self.setSession(sessionType=SessionType.BOT,
                            client=Client(name=communication_session_name_bot,
                                          api_id=apiId,
                                          api_hash=apiHash,
                                          bot_token=botToken))

            # client: Client = self.getSession(SessionType.BOT)
            self.sessionBot.add_handler(
                MessageHandler(callback=Communication.wellcomeProcedure, filters=filters.new_chat_members))

            self.sessionBot.add_handler(
                MessageHandler(callback=Communication.commandResponseStart,
                               filters=filters.command(commands=["start"]) & filters.private)
            )

            self.sessionBot.add_handler(
                MessageHandler(callback=Communication.commandResponseInfo,
                                 filters=filters.command(commands=["info"]) & filters.private)
            )

            # self._init()
            self.startSession(sessionType=SessionType.BOT)

            self.sessionBot.set_bot_commands([
                BotCommand("start", "Start the bot"),
                BotCommand("info", "get info about the bot")])

            self.isInitialized = True
            LOG.debug("... done!")
        except Exception as e:
            LOG.exception("Exception: " + str(e))
            raise CommunicationException("Exception: " + str(e))

    def _init(self):
        @self.sessionBot.on_message(filters=filters.new_chat_members)
        def log(client, message):
            print(message)

    def isInitialized(self) -> bool:
        return self.isInitialized

    def getSession(self, sessionType: SessionType) -> Client:
        LOG.info("Get session: " + str(sessionType))
        return self.sessionBot if sessionType == SessionType.BOT else self.sessionUser

    def setSession(self, sessionType: SessionType, client: Client):
        LOG.info("Set session: " + str(sessionType))
        if sessionType == SessionType.BOT:
            self.sessionBot = client
        else:
            self.sessionUser = client

    def startSession(self, sessionType: SessionType):
        LOG.info("Start session: " + str(sessionType))
        if sessionType == SessionType.BOT:
            self.sessionBot.start()
        else:
            self.sessionUser.start()

    def sendPhoto(self,
                  sessionType: SessionType,
                  chatId: (str, int),
                  photoPath: str,
                  caption: str = None,
                  replyMarkup: InlineKeyboardMarkup = None):
        try:
            assert isinstance(sessionType, SessionType), "SessionType should be SessionType"
            assert isinstance(chatId, (str, int)), "ChatId should be str"
            assert isinstance(photoPath, str), " photoPath should be str"
            assert isinstance(caption, (str, type(None))), "Caption should be str or None"
            LOG.info("Sending photo to: " + str(chatId))

            if sessionType == SessionType.BOT:
                self.sessionBot.send_photo(chat_id=chatId,
                                           photo=open(photoPath, 'rb'),
                                           caption=caption,
                                           reply_markup=replyMarkup)
            else:
                self.sessionUser.send_photo(chat_id=chatId,
                                            photo=open(photoPath, 'rb'),
                                            caption=caption,
                                            reply_markup=replyMarkup)

        except Exception as e:
            LOG.exception("Exception (in sendPhoto): " + str(e))

    def sendMessage(self,
                    sessionType: SessionType,
                    chatId: int,
                    text: str,
                    disableWebPagePreview=False,
                    scheduleDate: datetime = None,
                    inlineReplyMarkup: InlineKeyboardMarkup = None,
                    ) -> bool:
        # warning:
        # when sessionType is SessionType.USER you cannot send message with inline keyboard
        LOG.info("Send message to: " + str(chatId) + " with text: " + text
                 + " and scheduleDate: " + str(scheduleDate) if scheduleDate is not None else "<now>")
        try:
            assert isinstance(sessionType, SessionType), "SessionType should be SessionType"
            assert (sessionType is SessionType.BOT) or \
                   (sessionType is SessionType.USER and inlineReplyMarkup is None), \
                "when SessionType is USER there is no option to send inlineReplyMarkup!"
            if sessionType == SessionType.BOT:
                response = self.sessionBot.send_message(chat_id=chatId,
                                                        text=text,
                                                        schedule_date=scheduleDate,
                                                        reply_markup=inlineReplyMarkup,
                                                        disable_web_page_preview=disableWebPagePreview)
            else:
                response = self.sessionUser.send_message(chat_id=chatId,
                                                         text=text,
                                                         schedule_date=scheduleDate,
                                                         reply_markup=inlineReplyMarkup,
                                                         disable_web_page_preview=disableWebPagePreview)
            LOG.debug("Successfully send: " + "True" if type(response) is types.Message else "False")
            return True if type(response) is types.Message else False
        except FloodWait as e:
            LOG.exception("FloodWait exception (in sendMessage) Waiting time (in seconds): " + str(e.value))
            time.sleep(e.value)
            return self.sendMessage(sessionType=sessionType, chatId=chatId, text=text, replyMarkup=inlineReplyMarkup)
        except Exception as e:
            LOG.exception("Exception: " + str(e))

    def sendLogToAdmin(self, level: str, log: str):
        LOG.info("Sending log (level: " + level + ") to admin: " + log)
        if telegram_admins_id is not None:
            for adminId in telegram_admins_id:
                self.sendMessage(sessionType=SessionType.BOT, chatId=adminId, text=log)

    def createGroup(self, name: str, participants: list) -> int:
        LOG.info("Creating group: " + name + " with participants: " + str(participants))
        try:
            assert name is not None, "Name should not be null"
            assert participants is not None, "Participants should not be null"
            chat: Chat = self.sessionUser.create_group(title=name,
                                                       users=participants)

            return chat.id
        except Exception as e:
            LOG.exception("Exception (in createGroup): " + str(e))
            return None

    def createSuperGroup(self, name: str, description: str) -> int:
        LOG.info("Creating super group: " + name + " with description: " + description)
        try:
            assert name is not None, "Name should not be null"
            assert description is not None, "Description should not be null"
            chat: Chat = self.sessionUser.create_supergroup(title=name,
                                                            description=description)
            return chat.id
        except Exception as e:
            LOG.exception("Exception (in createSuperGroup): " + str(e))
            return None

    def getUsers(self, sessionType: SessionType) -> list:
        if sessionType == SessionType.BOT:
            kva = self.sessionBot.get_users(user_ids="me")
            return self.sessionBot.get_users()
        else:
            kva = self.sessionUser.get_users(user_ids="me")
            return self.sessionUser.get_users()

        return self.sessionUser.iter_participants(self.sessionUser.get_me())

    def getInvitationLink(self, sessionType: SessionType, chatId: int) -> str:
        assert isinstance(sessionType, SessionType), "sessionType should be SessionType"
        assert isinstance(chatId, int), "ChatId should be int"
        LOG.debug("Getting invitation link for chat: " + str(chatId) + " Make sure that user/bot is admin and keep in"
                                                                       "mind that link is valid until next call of this"
                                                                       "method. Previous link will be revoked.")
        LOG.info("Get invitation link for chat: " + str(chatId))
        try:
            inviteLink: str = self.sessionUser.export_chat_invite_link(chat_id=chatId) \
                if sessionType == SessionType.USER \
                else \
                self.sessionBot.export_chat_invite_link(chat_id=chatId)
            LOG.debug("Invite link: " + inviteLink)
            return inviteLink
        except Exception as e:
            LOG.exception("Exception (in getInvitationLink): " + str(e))
            return None

    def archiveGroup(self, chatId: int) -> bool:
        LOG.info("Archiving group: " + str(chatId))
        try:
            assert chatId is not None, "ChatId should not be null"
            self.sessionUser.archive_chat(chat_id=chatId)
            return True
        except Exception as e:
            LOG.exception("Exception (in archiveGroup): " + str(e))
            return False

    def callbackQuery(self, callbackQuery: types.CallbackQuery):
        LOG.info("Callback query: " + str(callbackQuery))
        try:
            # TODO: function in progress
            assert callbackQuery is not None, "CallbackQuery should not be null"
            # self.sessionBot.answer_callback_query(callback_query_id=callbackQuery.id)

            # self.sessionBot.on_callback_query(filters=filters.)

        except Exception as e:
            LOG.exception("Exception (in callbackQuery): " + str(e))

    def deleteGroup(self, chatId: int) -> bool:
        LOG.info("Deleting group: " + str(chatId))
        try:
            assert chatId is not None, "ChatId should not be null"
            self.sessionUser.delete_chat(chat_id=chatId)
            return True
        except Exception as e:
            LOG.exception("Exception (in deleteGroup): " + str(e))
            return False

    def addChatMembers(self, chatId: int, participants: list) -> bool:
        LOG.info("Adding participants to group: " + str(chatId) + " with participants: " + str(participants))
        try:
            assert chatId is not None, "ChatId should not be null"
            assert participants is not None, "Participants should not be null"
            self.sessionUser.add_chat_members(chat_id=chatId,
                                              user_ids=participants)
            return True
        except Exception as e:
            LOG.exception("Exception (in addChatMembers): " + str(e))
            return False

    def promoteMembers(self, sessionType: SessionType, chatId: int, participants: list) -> bool:
        LOG.info("Promoting participants to group: " + str(chatId) + " with participants: " + str(participants))
        try:
            assert isinstance(sessionType, SessionType), "SessionType should be SessionType"
            assert isinstance(chatId, int), "ChatId should be int"
            assert isinstance(participants, list), "Participants should be list"

            for participant in participants:
                try:
                    if sessionType == SessionType.USER:
                        self.sessionUser.promote_chat_member(chat_id=chatId,
                                                             user_id=participant,
                                                             privileges=ChatPrivileges(
                                                                 can_manage_chat=True,
                                                                 can_delete_messages=True,
                                                                 can_manage_video_chats=True,
                                                                 can_restrict_members=True,
                                                                 can_promote_members=True,
                                                                 can_change_info=True,
                                                                 can_invite_users=True,
                                                                 can_pin_messages=True,
                                                                 is_anonymous=False
                                                             )
                                                             )

                    else:
                        self.sessionBot.promote_chat_member(chat_id=chatId,
                                                            user_id=participant,
                                                            privileges=ChatPrivileges(
                                                                can_manage_chat=True,
                                                                can_delete_messages=True,
                                                                can_manage_video_chats=True,
                                                                can_restrict_members=True,
                                                                can_promote_members=True,
                                                                can_change_info=True,
                                                                can_invite_users=True,
                                                                can_pin_messages=True,
                                                                is_anonymous=False
                                                            )
                                                            )
                except Exception as e:
                    LOG.exception("Exception (in promoteMembers): " + str(e))
            return True
        except Exception as e:
            LOG.exception("Exception (in promoteMembers): " + str(e))
            return False

    def setChatDescription(self, chatId: int, description: str) -> bool:
        LOG.info("Setting description to group: " + str(chatId) + " with description: " + str(description))
        try:
            assert chatId is not None, "ChatId should not be null"
            assert description is not None, "Description should not be null"
            self.sessionUser.set_chat_description(chat_id=chatId,
                                                  description=description)
            return True
        except Exception as e:
            LOG.exception("Exception (in setChatDescription): " + str(e))
            return False

    def leaveChat(self, sessionType: SessionType, chatId: int) -> bool:
        assert isinstance(sessionType, SessionType), "SessionType should be SessionType"
        assert isinstance(chatId, int), "ChatId should be int"

        LOG.info("Leaving group: " + str(chatId))
        LOG.info("SessionType: " + str(sessionType))
        try:
            if sessionType == SessionType.USER:
                self.sessionUser.leave_chat(chat_id=chatId)
            else:
                self.sessionBot.leave_chat(chat_id=chatId)
            return True
        except Exception as e:
            LOG.exception("Exception (in leaveChat): " + str(e))
            return False

    #
    # Filters management
    #

    async def wellcomeProcedure(client: Client, message):
        try:
            LOG.success("New chat member: " + str(message.new_chat_members))
            chatid = message.chat.id
            LOG.success(".. in chat: " + str(chatid))
            database: Database = Database()
            for newMember in message.new_chat_members:
                if isinstance(newMember, types.User):
                    LOG.success("Wellcome message to user: " + str(newMember.id))
                    LOG.debug(
                        "... with username: " + str(newMember.username) if newMember.username is not None else "None")
                    LOG.debug("...name: " + str(newMember.first_name) if newMember.first_name is not None else "None")
                    LOG.debug(
                        "...last name: " + str(newMember.last_name) if newMember.last_name is not None else "None")

                    #if new member is a bot do nothing
                    if newMember.is_bot:
                        LOG.debug("...is bot. Do nothing")
                        continue

                    # promote only users who supposed to be in this room
                    participants: list[Participant] = database.getUsersInRoom(roomTelegramID=chatid)
                    if participants is None:
                        LOG.error("WellcomeProcedure; No participants in this room or room not found")
                        return
                    for participant in participants:
                        if participant.telegramID is not None and participant.telegramID == newMember.username:
                            LOG.debug(
                                "User supposed to be in this room: " + str(participant.telegramID) + " - promoting!")

                            wellcomeMessageObject: WellcomeMessageTextManagement = WellcomeMessageTextManagement()

                            await client.send_message(chat_id=chatid,
                                                      text=wellcomeMessageObject.getWellcomeMessage(
                                                          participantAccountName=str(participant.accountName)
                                                      ))

                            await client.promote_chat_member(chat_id=chatid,
                                                             user_id=newMember.username,
                                                             privileges=ChatPrivileges(
                                                                 can_manage_chat=True,
                                                                 can_delete_messages=True,
                                                                 can_manage_video_chats=True,
                                                                 can_restrict_members=True,
                                                                 can_promote_members=True,
                                                                 can_change_info=True,
                                                                 can_invite_users=True,
                                                                 can_pin_messages=True,
                                                                 is_anonymous=False
                                                             ))
                            LOG.success(
                                "Promoting  user " + str(participant.telegramID) + " to admin successfully done!")
                            break
                else:
                    LOG.success("New member is not instance of 'User'")
        except Exception as e:
            LOG.exception("Exception (in wellcomeProcedure): " + str(e))
            return

    async def commandResponseStart(client: Client, message):
        try:
            LOG.success("Response on command 'start' from user: " + str(message.chat.username) if not None else "None")
            chatid = message.chat.id
            LOG.success(".. in chat: " + str(chatid))

            database: Database = Database()
            if isinstance(message.chat.username, str):
                LOG.debug("Username exists: " + str(message.chat.username))

            participant: Participant = database.getParticipantByTelegramID(telegramID=message.chat.username)

            # reply_markup=inlineReplyMarkup, disable_web_page_preview=disableWebPagePreview

            botCommunicationManagement: BotCommunicationManagement = BotCommunicationManagement()
            telegramID: str = "@" + str(message.chat.username) if message.chat.username is not None else None
            if participant is None:
                LOG.error("Participant not found in database")
                await client.send_message(chat_id=chatid,
                                          text=botCommunicationManagement.startCommandNotKnownTelegramID(
                                              telegramID=telegramID),
                                          reply_markup=InlineKeyboardMarkup(
                                              inline_keyboard=
                                              [
                                                  [
                                                      InlineKeyboardButton(
                                                          text=botCommunicationManagement.startCommandNotKnownTelegramIDButtonText(),
                                                          url=eden_support_url),

                                                  ]
                                              ]
                                          )
                                          )

            else:
                LOG.debug("Participant found in database")
                await client.send_message(chat_id=chatid,
                                          text=botCommunicationManagement.startCommandKnownTelegramID(
                                              telegramID=telegramID))

        except Exception as e:
            LOG.exception("Exception (in commandResponseStart): " + str(e))
            return

    async def commandResponseInfo(client: Client, message):
        try:
            LOG.success("Response on command 'info' from user: " + str(message.chat.username) if not None else "None")
            chatid = message.chat.id
            LOG.success(".. in chat: " + str(chatid))

            database: Database = Database()
            if isinstance(message.chat.username, str):
                LOG.debug("Username exists: " + str(message.chat.username))

            participant: Participant = database.getParticipantByTelegramID(telegramID=message.chat.username)

            botCommunicationManagement: BotCommunicationManagement = BotCommunicationManagement()
            await client.send_message(chat_id=chatid,
                                      text=botCommunicationManagement.infoCommand(),
                                      reply_markup=InlineKeyboardMarkup(
                                          inline_keyboard=
                                          [
                                              [
                                                  InlineKeyboardButton(
                                                      text=botCommunicationManagement.infoCommandButtonText(),
                                                      url=eden_portal_url),

                                              ]
                                          ]
                                      )
                                      )

        except Exception as e:
            LOG.exception("Exception (in commandResponseStart): " + str(e))
            return

    def idle(self):
        idle()

    def setFilters(self):
        # not in  use
        LOG.info("Set filters: " + str(filters))
        client: Client = self.getSession(SessionType.BOT)
        # client1: Client = self.getSession(SessionType.USER)

        client.add_handler(MessageHandler(callback=Communication.wellcomeProcedure))  # """, filters=filters.text"""
        # client.run()

        idle()

        ######

        async def welcome(bot, message):
            LOG.success("New chat member: " + str(message.new_chat_members))
            chatid = message.chat.id
            LOG.success(".. in chat: " + str(chatid))
            await bot.send_message(text=f"Welcome {message.from_user.mention} to {message.chat.username}",
                                   chat_id=chatid)
            database: Database = Database()

            # promote only users who supposed to be in this room
            participants: list[Participant] = database.getUsersInRoom(roomTelegramID=chatid)
            for participant in participants:
                if participant.telegramID is not None and \
                        participant.telegramID == message.chat.username:
                    LOG.debug("User supposed to be in this room: " + str(participant.telegramID) + " - promoting!")
                    bot.promoteMembers(chatId=chatid, participants=[message.chat.username])


def runPyrogram():
    comm = Communication()
    comm.start(apiId=telegram_api_id, apiHash=telegram_api_hash, botToken=telegram_bot_token)
    # chatID = comm.createSuperGroup(name="test1", description="test1")
    # print("Newly created chat id: " + str(chatID)) #test1 - 1001893075719

    comm.sendPhoto(sessionType=SessionType.BOT,
                   chatId="test",
                   caption="test",
                   photoPath=open('../../assets/startVideoPreview1.png'))

    chatID = -1001893075719
    botID = 1
    botName = "@up_vote_demo_bot"
    userID = 1
    # first intecation
    """comm.sendMessage(sessionType=SessionType.USER, chatId=botName, text="From bot <br/> to user \n with new line"
                                                                        "and \\n new line")

    gctm = GroupCommunicationTextManagement()
    buttons: tuple[Button] = gctm.invitationLinkToTheGroupButons(groupLink="https://t.me/+iCrYgZ_rgqxmZGE0")

    comm.sendMessage(sessionType=SessionType.BOT, chatId="@EdenElectionSupport",
                     text=gctm.invitationLinkToTheGroup(round=1),
                     inlineReplyMarkup=InlineKeyboardMarkup(
                         inline_keyboard=
                         [
                             [
                                 InlineKeyboardButton(text=buttons[0]['text'],
                                                      url=buttons[0]['value']),

                             ]
                         ]
                     )
                     )

    print("chatID: " + str(chatID))
    print(chatID)
    print("------")
    comm.addChatMembers(chatId=chatID, participants=["@edenElectionSupport", "@nejcSkerjanc2", botName])
    # comm.promoteMembers(chatId=chatID, participants=[botName, "@edenElectionSupport"])
    comm.sendMessage(sessionType=SessionType.USER,
                     chatId=chatID,
                     text="Hope you will get next messages in next few minutes!")
    comm.sendMessage(sessionType=SessionType.USER,
                     chatId=chatID,
                     text="I am bot  - bot, i am 30 seconds ahead in the future:)",
                     scheduleDate=DateTimeManagement.getUnixTimestampInDT() + timedelta(seconds=30))
    comm.sendMessage(sessionType=SessionType.USER,
                     chatId=chatID,
                     text="I am bot  - bot, i am 60 seconds ahead in the future:)",
                     scheduleDate=DateTimeManagement.getUnixTimestampInDT() + timedelta(seconds=60))

    comm.sendMessage(sessionType=SessionType.USER,
                     chatId=chatID,
                     text="I am leaving now!")

    comm.leaveChat(sessionType=SessionType.USER, chatId=chatID)
    
    comm.idle()"""


def main():
    ###########################################
    # multiprocessing
    pyogram = Process(target=runPyrogram)
    pyogram.start()
    #############################################

    while True:
        time.sleep(3)
        print("main Thread")
    i = 9


if __name__ == "__main__":
    main()
