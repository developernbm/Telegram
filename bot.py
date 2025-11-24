import asyncio
import random
import time
import csv
import json
from telethon import TelegramClient, functions, types, events
from telethon.tl.functions.channels import InviteToChannelRequest, GetParticipantsRequest
from telethon.tl.types import ChannelParticipantsSearch, InputChannel
from telethon.tl.functions.contacts import ResolveUsernameRequest
from telethon.network import ConnectionTcpAbridged
import logging
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
import requests

# Configure advanced logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("ctf_telegram_advanced.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AdvancedTelegramCTFSolver:
    def __init__(self):
        self.clients = []
        self.current_client_index = 0
        self.proxies = self.load_proxies()
        self.user_agents = self.generate_user_agents(100)
        self.user_data = {}
        self.bot_client = None
        self.active_conversations = {}
        
    def load_proxies(self):
        """Load proxies from file or API"""
        try:
            proxies = []
            try:
                with open('proxies.txt', 'r') as f:
                    proxies = [line.strip() for line in f if line.strip()]
            except:
                logger.warning("No proxies file found, using direct connection")
            
            return proxies
        except Exception as e:
            logger.error(f"Error loading proxies: {e}")
            return []
    
    def generate_user_agents(self, count):
        """Generate random user agents"""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/91.0.864.59"
        ]
        return user_agents * (count // len(user_agents) + 1)
    
    def get_random_user_agent(self):
        """Get a random user agent"""
        return random.choice(self.user_agents) if self.user_agents else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    
    def get_random_proxy(self):
        """Get a random proxy from the list"""
        return random.choice(self.proxies) if self.proxies else None
    
    async def initialize_bot(self):
        """Initialize the bot client with hardcoded token"""
        try:
            # Using the provided bot token directly
            BOT_TOKEN = "8265774665:AAF7SuJeih_yQoW_fhEypfliS3DZaE2vfho"
            
            self.bot_client = TelegramClient(
                'bot_session', 
                1,  # Dummy API ID for bot
                'dummy_hash',  # Dummy API hash for bot
                connection=ConnectionTcpAbridged
            )
            
            await self.bot_client.start(bot_token=BOT_TOKEN)
            
            if await self.bot_client.is_user_authorized():
                logger.info("Bot client initialized successfully")
                me = await self.bot_client.get_me()
                logger.info(f"Bot started as @{me.username}")
                return True
            else:
                logger.error("Bot client not authorized")
                return False
                
        except Exception as e:
            logger.error(f"Failed to initialize bot client: {e}")
            return False
    
    async def initialize_user_clients(self, api_ids, api_hashes, phone_numbers, session_names=None):
        """Initialize multiple Telegram clients for parallel operations"""
        self.api_ids = api_ids if isinstance(api_ids, list) else [api_ids]
        self.api_hashes = api_hashes if isinstance(api_hashes, list) else [api_hashes]
        self.phone_numbers = phone_numbers if isinstance(phone_numbers, list) else [phone_numbers]
        
        if session_names is None:
            self.session_names = [f"ctf_session_{i}" for i in range(len(self.phone_numbers))]
        else:
            self.session_names = session_names if isinstance(session_names, list) else [session_names]
        
        for i, (api_id, api_hash, phone, session_name) in enumerate(zip(
            self.api_ids, self.api_hashes, self.phone_numbers, self.session_names
        )):
            try:
                proxy = self.get_random_proxy()
                proxy_dict = None
                
                if proxy:
                    if proxy.startswith('http'):
                        proxy_dict = {'proxy_type': 'http', 'addr': proxy}
                    elif proxy.startswith('socks5'):
                        proxy_dict = {'proxy_type': 'socks5', 'addr': proxy}
                
                client = TelegramClient(
                    session_name, 
                    api_id, 
                    api_hash,
                    connection=ConnectionTcpAbridged,
                    proxy=proxy_dict,
                    device_model=f"CTF Device {i}",
                    system_version="CTF OS 1.0",
                    app_version="CTF App 1.0",
                    system_lang_code="en",
                    lang_code="en"
                )
                
                await client.start(phone=phone)
                
                if await client.is_user_authorized():
                    self.clients.append(client)
                    logger.info(f"Client {i} initialized successfully with phone {phone}")
                else:
                    logger.error(f"Client {i} not authorized")
                    
            except Exception as e:
                logger.error(f"Failed to initialize client {i}: {e}")
        
        return len(self.clients) > 0
    
    def get_client(self):
        """Get a client with round-robin selection"""
        if not self.clients:
            return None
        
        client = self.clients[self.current_client_index]
        self.current_client_index = (self.current_client_index + 1) % len(self.clients)
        return client
    
    async def ask_user_for_input(self, user_id, question, is_list=False):
        """Ask user a question and wait for response"""
        # Send the question
        await self.bot_client.send_message(user_id, question)
        
        # Store the conversation state
        self.active_conversations[user_id] = {
            'waiting_for_response': True,
            'expected_type': 'list' if is_list else 'text'
        }
        
        # Wait for response with timeout
        start_time = time.time()
        while time.time() - start_time < 300:  # 5 minutes timeout
            if user_id in self.active_conversations and not self.active_conversations[user_id]['waiting_for_response']:
                response = self.active_conversations[user_id].get('response')
                del self.active_conversations[user_id]
                return response
            await asyncio.sleep(1)
        
        # Timeout
        if user_id in self.active_conversations:
            del self.active_conversations[user_id]
        await self.bot_client.send_message(user_id, "⏰ Timeout waiting for your response. Please start over with /start")
        return None
    
    async def handle_user_response(self, event):
        """Handle user responses for active conversations"""
        user_id = event.sender_id
        if user_id in self.active_conversations and self.active_conversations[user_id]['waiting_for_response']:
            if self.active_conversations[user_id]['expected_type'] == 'list':
                # Split by comma and strip whitespace
                response = [item.strip() for item in event.text.split(',')]
            else:
                response = event.text
            
            self.active_conversations[user_id]['response'] = response
            self.active_conversations[user_id]['waiting_for_response'] = False
    
    async def start_conversation(self, event):
        """Start conversation with user to collect all required information"""
        try:
            user_id = event.sender_id
            
            # Check if user is already in a conversation
            if user_id in self.active_conversations:
                await event.respond("⚠️ You already have an active conversation. Please complete it first.")
                return
            
            self.user_data[user_id] = {}
            
            await event.respond(
                "🤖 **Advanced Telegram CTF Solver Bot**\n\n"
                "I will help you with the CTF challenge. Let's collect the required information step by step.\n\n"
                "Please provide the following information:"
            )
            
            # Ask for API IDs
            api_ids_input = await self.ask_user_for_input(
                user_id,
                "🆔 **Step 1/5:** Please enter your API IDs (comma-separated if multiple):\n\nExample: `123456, 234567, 345678`",
                is_list=True
            )
            if not api_ids_input:
                return
            
            try:
                api_ids = [int(api_id.strip()) for api_id in api_ids_input]
            except ValueError:
                await event.respond("❌ Invalid API IDs. Please enter numbers only. Start over with /start")
                return
            
            self.user_data[user_id]['api_ids'] = api_ids
            
            # Ask for API Hashes
            api_hashes = await self.ask_user_for_input(
                user_id,
                "🔒 **Step 2/5:** Please enter your API Hashes (comma-separated if multiple):\n\nExample: `abc123def456, xyz789uvw012, hash1hash2hash3`",
                is_list=True
            )
            if not api_hashes:
                return
            
            self.user_data[user_id]['api_hashes'] = api_hashes
            
            # Ask for Phone Numbers
            phone_numbers = await self.ask_user_for_input(
                user_id,
                "📱 **Step 3/5:** Please enter your phone numbers (comma-separated if multiple):\n\nExample: `+1234567890, +0987654321, +1112223333`",
                is_list=True
            )
            if not phone_numbers:
                return
            
            self.user_data[user_id]['phone_numbers'] = phone_numbers
            
            # Ask for Source Groups
            source_groups = await self.ask_user_for_input(
                user_id,
                "📂 **Step 4/5:** Please enter source group usernames (comma-separated):\n\nExample: `@group1, @group2, group3`",
                is_list=True
            )
            if not source_groups:
                return
            
            # Ensure groups start with @
            source_groups = [f"@{group.replace('@', '')}" for group in source_groups]
            self.user_data[user_id]['source_groups'] = source_groups
            
            # Ask for Target Group
            target_group = await self.ask_user_for_input(
                user_id,
                "🎯 **Step 5/5:** Please enter the target group username:\n\nExample: `@targetgroup` or `targetgroup`"
            )
            if not target_group:
                return
            
            # Ensure target group starts with @
            if not target_group.startswith('@'):
                target_group = f"@{target_group}"
            self.user_data[user_id]['target_group'] = target_group
            
            # Confirm and start
            await event.respond(
                f"✅ **All information collected!**\n\n"
                f"• 📊 API IDs: {len(api_ids)} accounts\n"
                f"• 📂 Source Groups: {', '.join(source_groups)}\n"
                f"• 🎯 Target Group: {target_group}\n\n"
                f"🚀 Starting the CTF challenge..."
            )
            
            # Initialize user clients
            await event.respond("🔄 Initializing user clients...")
            if not await self.initialize_user_clients(api_ids, api_hashes, phone_numbers):
                await event.respond("❌ Failed to initialize user clients. Please check your credentials and try again with /start")
                return
            
            await event.respond(f"✅ Successfully initialized {len(self.clients)} user clients!")
            
            # Run the challenge
            member_limit = 100
            success = await self.run_advanced_challenge(
                source_groups, 
                target_group, 
                member_limit,
                event
            )
            
            if success:
                await event.respond("🎉 **CTF Challenge Completed Successfully!**")
            else:
                await event.respond("❌ **CTF Challenge Failed.** Check the logs for details.")
            
        except Exception as e:
            logger.error(f"Error in conversation: {e}")
            await event.respond(f"❌ An error occurred: {str(e)}\n\nPlease start over with /start")
    
    async def advanced_resolve_group(self, group_identifier):
        """Advanced group resolution with multiple fallbacks"""
        clients_to_try = self.clients.copy()
        random.shuffle(clients_to_try)
        
        for client in clients_to_try:
            try:
                if isinstance(group_identifier, str):
                    if group_identifier.startswith('@'):
                        group = await client(ResolveUsernameRequest(group_identifier[1:]))
                    else:
                        group = await client(ResolveUsernameRequest(group_identifier))
                else:
                    group = await client.get_entity(group_identifier)
                
                if group:
                    logger.info(f"Successfully resolved group {group_identifier} with client {client.session.filename}")
                    return group
                    
            except Exception as e:
                logger.warning(f"Failed to resolve group {group_identifier} with client {client.session.filename}: {e}")
                continue
        
        logger.error(f"All clients failed to resolve group {group_identifier}")
        return None
    
    async def stealth_get_members(self, group_identifier, limit=200, delay_between=2):
        """Stealthy member retrieval with randomized patterns"""
        try:
            group = await self.advanced_resolve_group(group_identifier)
            if not group:
                return []
            
            members = []
            offset = 0
            batch_size = min(100, limit)
            
            while len(members) < limit and offset < 10000:
                client = self.get_client()
                if not client:
                    break
                
                try:
                    participants = await client(GetParticipantsRequest(
                        channel=group,
                        filter=ChannelParticipantsSearch(''),
                        offset=offset,
                        limit=batch_size,
                        hash=0
                    ))
                    
                    if not participants or not participants.users:
                        break
                    
                    members.extend(participants.users)
                    offset += batch_size
                    
                    delay = random.uniform(delay_between, delay_between * 2)
                    await asyncio.sleep(delay)
                    
                    batch_size = random.randint(50, min(200, limit - len(members)))
                    
                except Exception as e:
                    logger.warning(f"Error retrieving batch: {e}")
                    continue
            
            unique_members = list({member.id: member for member in members}.values())
            logger.info(f"Retrieved {len(unique_members)} unique members from {group_identifier}")
            return unique_members[:limit]
            
        except Exception as e:
            logger.error(f"Failed to get members from {group_identifier}: {e}")
            return []
    
    async def advanced_add_members(self, members, target_group_identifier, max_workers=5, event=None):
        """Advanced member adding with parallel processing"""
        try:
            target_group = await self.advanced_resolve_group(target_group_identifier)
            if not target_group:
                if event:
                    await event.respond(f"❌ Failed to resolve target group: {target_group_identifier}")
                return False
            
            success_count = 0
            fail_count = 0
            skipped_count = 0
            
            valid_members = [m for m in members if hasattr(m, 'id') and m.id]
            
            if event:
                await event.respond(f"🔄 Starting to add {len(valid_members)} members to {target_group_identifier}...")
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                loop = asyncio.get_event_loop()
                tasks = []
                
                for i, member in enumerate(valid_members):
                    task = loop.run_in_executor(
                        executor, 
                        self._add_member_sync, 
                        member, 
                        target_group,
                        i + 1,
                        len(valid_members)
                    )
                    tasks.append(task)
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for result in results:
                    if isinstance(result, Exception):
                        fail_count += 1
                    elif result is True:
                        success_count += 1
                    else:
                        skipped_count += 1
            
            logger.info(f"Added {success_count} members successfully. Failed: {fail_count}. Skipped: {skipped_count}")
            
            if event:
                await event.respond(
                    f"✅ **Member adding completed!**\n\n"
                    f"• ✅ Success: {success_count}\n"
                    f"• ❌ Failed: {fail_count}\n"
                    f"• ⏭️ Skipped: {skipped_count}"
                )
            
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Failed to add members to {target_group_identifier}: {e}")
            if event:
                await event.respond(f"❌ Failed to add members: {str(e)}")
            return False
    
    def _add_member_sync(self, member, target_group, current, total):
        """Synchronous member adding for thread pool"""
        try:
            client = self.get_client()
            if not client:
                return False
            
            delay = random.uniform(5, 15)
            time.sleep(delay)
            
            with client:
                client.loop.run_until_complete(client(InviteToChannelRequest(
                    channel=target_group,
                    users=[member]
                )))
            
            logger.info(f"Successfully added user {member.id} to group ({current}/{total})")
            return True
            
        except Exception as e:
            logger.warning(f"Failed to add user {member.id}: {e}")
            return False
    
    def web_scrape_members(self, group_username, max_members=100):
        """Alternative method: scrape members from web interface using requests"""
        try:
            headers = {
                'User-Agent': self.get_random_user_agent(),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            }
            
            url = f"https://t.me/{group_username.replace('@', '')}"
            
            # Use proxy if available
            proxies = None
            proxy = self.get_random_proxy()
            if proxy:
                proxies = {
                    'http': proxy,
                    'https': proxy
                }
            
            response = requests.get(url, headers=headers, proxies=proxies, timeout=30)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                members = []
                
                # Look for member count or user elements
                member_elements = soup.find_all(['div', 'span'], 
                                              class_=lambda x: x and any(word in x.lower() for word in ['member', 'subscriber', 'user', 'tgme']))
                
                for elem in member_elements[:max_members]:
                    text = elem.get_text()
                    if any(word in text.lower() for word in ['member', 'subscriber', 'user']):
                        # Extract numbers from text (for member counts)
                        import re
                        numbers = re.findall(r'\d+', text.replace(',', '').replace('.', ''))
                        if numbers:
                            members.append({'member_count': int(numbers[0])})
                
                logger.info(f"Web scraped member info from {group_username}")
                return members
            else:
                logger.warning(f"Web scraping failed with status code: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Web scraping failed: {e}")
            return []
    
    async def run_advanced_challenge(self, source_groups, target_group, member_limit=100, event=None):
        """Advanced CTF challenge runner with multiple strategies"""
        if event:
            await event.respond("🚀 Starting advanced CTF challenge...")
        logger.info("Starting advanced CTF challenge...")
        
        all_members = []
        
        # Strategy 1: Use Telethon to get members
        for group in source_groups:
            if event:
                await event.respond(f"📂 Retrieving members from {group}...")
            logger.info(f"Retrieving members from {group} using Telethon")
            members = await self.stealth_get_members(group, member_limit)
            all_members.extend(members)
            
            if event:
                await event.respond(f"✅ Retrieved {len(members)} members from {group}")
            
            await asyncio.sleep(random.uniform(10, 30))
        
        # Strategy 2: Web scraping fallback (sync version)
        if len(all_members) < member_limit * len(source_groups) * 0.5:
            if event:
                await event.respond("🕸️ Getting additional info via web scraping...")
            logger.info("Using web scraping for additional info")
            for group in source_groups:
                # Run sync function in thread pool
                loop = asyncio.get_event_loop()
                scraped_members = await loop.run_in_executor(
                    None, 
                    self.web_scrape_members, 
                    group, 
                    member_limit // 2
                )
                logger.info(f"Web scraped info: {scraped_members}")
        
        # Remove duplicates
        unique_members = list({member.id: member for member in all_members}.values())
        logger.info(f"Found {len(unique_members)} unique members")
        
        if event:
            await event.respond(f"📊 Found {len(unique_members)} unique members total")
        
        # Export members to CSV for documentation
        self.export_members_to_csv(unique_members, "ctf_members_advanced.csv")
        
        # Add members to target group with parallel processing
        if event:
            await event.respond(f"👥 Adding {len(unique_members)} members to {target_group}...")
        logger.info(f"Adding {len(unique_members)} members to {target_group}")
        
        result = await self.advanced_add_members(unique_members, target_group, max_workers=3, event=event)
        
        if result:
            success_msg = "🎉 Advanced CTF challenge completed successfully!"
            logger.info(success_msg)
            self.generate_advanced_report(source_groups, target_group, len(unique_members))
        else:
            error_msg = "❌ Advanced CTF challenge failed!"
            logger.error(error_msg)
        
        return result
    
    def export_members_to_csv(self, members, filename='ctf_members_advanced.csv'):
        """Export member data to a CSV file"""
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['user_id', 'first_name', 'last_name', 'username']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for member in members:
                    writer.writerow({
                        'user_id': member.id,
                        'first_name': member.first_name or '',
                        'last_name': member.last_name or '',
                        'username': member.username or ''
                    })
            
            logger.info(f"Exported {len(members)} members to {filename}")
            return True
        except Exception as e:
            logger.error(f"Failed to export members to CSV: {e}")
            return False
    
    def generate_advanced_report(self, source_groups, target_group, members_added):
        """Generate an advanced CTF challenge report"""
        report = {
            "challenge_name": "Telegram Members Adder CTF",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "source_groups": source_groups,
            "target_group": target_group,
            "members_added": members_added,
            "clients_used": len(self.clients),
            "status": "SUCCESS" if members_added > 0 else "FAILED"
        }
        
        with open('ctf_challenge_report.json', 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Generated advanced report")
        return report

# Main bot handler
async def main():
    solver = AdvancedTelegramCTFSolver()
    
    print("🤖 Starting Telegram Bot...")
    if not await solver.initialize_bot():
        print("❌ Failed to initialize bot. Exiting.")
        return
    
    print("✅ Bot started successfully! Waiting for messages...")
    
    @solver.bot_client.on(events.NewMessage(pattern='/start'))
    async def start_handler(event):
        await solver.start_conversation(event)
    
    @solver.bot_client.on(events.NewMessage)
    async def message_handler(event):
        if event.text and event.text.startswith('/'):
            return
        await solver.handle_user_response(event)
    
    @solver.bot_client.on(events.NewMessage(pattern='/help'))
    async def help_handler(event):
        await event.respond(
            "🤖 **Advanced Telegram CTF Solver Bot**\n\n"
            "**Commands:**\n"
            "• /start - Start the CTF challenge\n"
            "• /help - Show this help\n\n"
            "I'll help you transfer members between Telegram groups!"
        )
    
    await solver.bot_client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
