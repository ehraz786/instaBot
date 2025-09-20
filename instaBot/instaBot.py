import instaloader
import os
import shutil
import glob
import re
import asyncio
from telebot.async_telebot import AsyncTeleBot

API_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN'
bot = AsyncTeleBot(API_TOKEN)

# Absolute path to the folder where the script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Folder to save videos
DOWNLOADS_DIR = os.path.join(BASE_DIR, ".data-files", "downloads")

# Path to session file
SESSION_FILE_PATH = os.path.join(BASE_DIR, ".data-files", "session-file", "YOUR_SESSION_FILE")

# Make sure the folder exists
os.makedirs(DOWNLOADS_DIR, exist_ok=True)
os.makedirs(SESSION_FILE_PATH, exist_ok=True)

# Helper function to sort files based on Instagram's naming convention
def sort_key_instaloader(filename):
    """
    A custom sort key function for instaloader filenames.
    It looks for '_1', '_2', etc., in the filename to determine the correct order.
    """
    match = re.search(r'_(\d+)\.(jpg|mp4)$', filename)
    if match:
        # If a number is found (e.g., '_1.jpg'), return that number
        return int(match.group(1))
    # The first item in a carousel often has no number, so it should come first
    return 0

# Handles Incoming Start Command
@bot.message_handler(commands=['start'])
async def send_welcome(message):

    await bot.send_chat_action(message.chat.id, "typing")
    await bot.reply_to(message, "Hi! Send me an instagram link to download.")
                 
@bot.message_handler(func=lambda message: True)
async def message_handler(message):

    if 'instagram.com/reel/' in message.text:
        # ✅ Initialize Instaloader locally for this specific request
        L = instaloader.Instaloader(
            dirname_pattern=os.path.join(DOWNLOADS_DIR, "{target}"),
            save_metadata=False,
            download_comments=False
        )

        url = message.text.strip()
        await bot.send_chat_action(message.chat.id, "typing")
        status_msg = await bot.reply_to(message, "📥 Downloading reel... Please wait.")

        try:
            # Extract shortcode from URL
            shortcode = url.split('/reel/')[1].split('/')[0]

            # Set Download directory
            target_dir = os.path.join(DOWNLOADS_DIR, shortcode)

            # Download using instaloader
            post = instaloader.Post.from_shortcode(L.context, shortcode)
            L.download_post(post, target=shortcode)

            # Find the downloaded mp4 file
            mp4_files = glob.glob(os.path.join(target_dir, "*.mp4"), recursive=True)

            if not mp4_files:
                await bot.edit_message_text("❌ Could not find the video file.", chat_id=message.chat.id, message_id=status_msg.message_id)
                return
            
            await bot.edit_message_text(chat_id=message.chat.id, message_id=status_msg.message_id, text="🎬 Here's your reel! 👇🏻")
            await bot.send_chat_action(message.chat.id, "upload_video")

            video_path = mp4_files[0]
            with open(video_path, 'rb') as video:
                await bot.send_video(message.chat.id, video)

        except instaloader.exceptions.ConnectionException as e:
            pass

        except instaloader.exceptions.InstaloaderException as e:
            # --- FIRST ATTEMPT FAILED, TRYING AGAIN LOGGED IN ---
            await bot.edit_message_text("⚠️ Anonymous download failed. Retrying with a logged-in session...", chat_id=message.chat.id, message_id=status_msg.message_id)
        
            try:
                # Load session into the existing local instance
                L.load_session_from_file(username=None, filename=SESSION_FILE_PATH)

                # Retry Download
                post = instaloader.Post.from_shortcode(L.context, shortcode)
                L.download_post(post, target=shortcode)

                # Find the downloaded mp4 file
                mp4_files = glob.glob(os.path.join(target_dir, "*.mp4"), recursive=True)

                if not mp4_files:
                    await bot.edit_message_text("❌ Could not find the video file.", chat_id=message.chat.id, message_id=status_msg.message_id)
                    return
                
                await bot.edit_message_text(chat_id=message.chat.id, message_id=status_msg.message_id, text="🎬 Here's your reel! 👇🏻")
                await bot.send_chat_action(message.chat.id, "upload_video")

                video_path = mp4_files[0]
                with open(video_path, 'rb') as video:
                    await bot.send_video(message.chat.id, video)

            except Exception as final_e:
                await bot.edit_message_text(f"❌ Login successful, but still could not download.\n`{final_e}`", chat_id=message.chat.id, message_id=status_msg.message_id)        

        except Exception as e:
            await bot.edit_message_text(f"❌ Failed to download: {str(e)}", chat_id=message.chat.id, message_id=status_msg.message_id)

        finally:
            if os.path.exists(target_dir):
                shutil.rmtree(target_dir, ignore_errors=True)     

    elif 'instagram.com/p/' in message.text:
        # ✅ Initialize Instaloader locally for this specific request
        L = instaloader.Instaloader(
            dirname_pattern=os.path.join(DOWNLOADS_DIR, "{target}"),
            save_metadata=False,
            download_comments=False
        )

        url = message.text.strip()

        # Check for a specific image index in the URL
        img_index = None
        if '?img_index=' in url:
            try:
                index_str = url.split('?img_index=')[1].split('&')[0]
                img_index = int(index_str)

            except (ValueError, IndexError):
                pass # Ignore if parsing fails, will default to downloading all
        
        await bot.send_chat_action(message.chat.id, "typing")
        status_msg = await bot.reply_to(message, "📥 Downloading post... Please wait.")

        try:
            shortcode = url.split('/p/')[1].split('/')[0]
            target_dir = os.path.join(DOWNLOADS_DIR, shortcode)

            post = instaloader.Post.from_shortcode(L.context, shortcode)
            L.download_post(post, target=shortcode)

            media_files = glob.glob(os.path.join(target_dir, "*.jpg")) + \
                glob.glob(os.path.join(target_dir, "*.mp4"))
            
            #media_files.sort()
            # Use the custom sort function instead of a simple .sort()
            media_files.sort(key=sort_key_instaloader)

            if not media_files:
                await bot.edit_message_text("❌ Could not find any media in this post.", chat_id=message.chat.id, message_id=status_msg.message_id)
                return
            
            await bot.edit_message_text(f"🎬 Here's your post! 👇🏻", chat_id=message.chat.id, message_id=status_msg.message_id)

            files_to_send = []
            if img_index is not None:
                # User wants a specific item
                if 0 <= img_index < len(media_files):
                    # Valid index, select the specific file (adjust for 0-based index)
                    files_to_send.append(media_files[img_index])
                    #await bot.edit_message_text(f"📤 Found {len(media_files)} item(s). Uploading item #{img_index}...", chat_id=message.chat.id, message_id=status_msg.message_id)
                else:
                    # Invalid index
                    await bot.edit_message_text(f"❌ Invalid index. This post has {len(media_files)} items, but you requested item #{img_index}.", chat_id=message.chat.id, message_id=status_msg.message_id)
                    return # Stop execution
            else:
                # No specific index, send all files
                files_to_send = media_files

            # Loop through the selected files and send them       
            for media_path in files_to_send:
                with open(media_path, 'rb') as file:
                    if media_path.endswith(".jpg"):
                        await bot.send_photo(message.chat.id, file)
                    elif media_path.endswith(".mp4"):
                        await bot.send_video(message.chat.id, file)

        except instaloader.exceptions.ConnectionException as e:
            pass

        except instaloader.exceptions.InstaloaderException as e:
            # --- FIRST ATTEMPT FAILED, TRYING AGAIN LOGGED IN ---
            await bot.edit_message_text("⚠️ Anonymous download failed. Retrying with a logged-in session...", chat_id=message.chat.id, message_id=status_msg.message_id)
            
            try:
                # Load session into the existing local instance
                L.load_session_from_file(username=None, filename=SESSION_FILE_PATH)

                # Retry Download
                post = instaloader.Post.from_shortcode(L.context, shortcode)
                L.download_post(post, target=shortcode)

                media_files = glob.glob(os.path.join(target_dir, "*.jpg")) + \
                glob.glob(os.path.join(target_dir, "*.mp4"))
            
                #media_files.sort()
                # Use the custom sort function instead of a simple .sort()
                media_files.sort(key=sort_key_instaloader)

                if not media_files:
                    await bot.edit_message_text("❌ Could not find any media in this post.", chat_id=message.chat.id, message_id=status_msg.message_id)
                    return
            
                await bot.edit_message_text(f"🎬 Here's your post! 👇🏻", chat_id=message.chat.id, message_id=status_msg.message_id)

                files_to_send = []
                if img_index is not None:
                    # User wants a specific item
                    if 0 <= img_index < len(media_files):
                        # Valid index, select the specific file (adjust for 0-based index)
                        files_to_send.append(media_files[img_index])
                        #await bot.edit_message_text(f"📤 Found {len(media_files)} item(s). Uploading item #{img_index}...", chat_id=message.chat.id, message_id=status_msg.message_id)
                    else:
                        # Invalid index
                        await bot.edit_message_text(f"❌ Invalid index. This post has {len(media_files)} items, but you requested item #{img_index}.", chat_id=message.chat.id, message_id=status_msg.message_id)
                        return # Stop execution
                else:
                    # No specific index, send all files
                    files_to_send = media_files

                # Loop through the selected files and send them       
                for media_path in files_to_send:
                    with open(media_path, 'rb') as file:
                        if media_path.endswith(".jpg"):
                            await bot.send_photo(message.chat.id, file)
                        elif media_path.endswith(".mp4"):
                            await bot.send_video(message.chat.id, file)
            
            except Exception as final_e:
                await bot.edit_message_text(f"❌ Login successful, but still could not download.\n`{final_e}`", chat_id=message.chat.id, message_id=status_msg.message_id)

        except Exception as e:
            await bot.edit_message_text(f"An unexpected error occurred: {e}", chat_id=message.chat.id, message_id=status_msg.message_id)

        finally:
            if os.path.exists(target_dir):
                shutil.rmtree(target_dir, ignore_errors=True)                

    elif 'instagram.com/stories/' in message.text:
        await bot.send_chat_action(message.chat.id, "typing")
        await bot.reply_to(message, "🔜 Story link detected, Feature is not available yet.")    

    else:
        await bot.send_chat_action(message.chat.id, "typing")
        await bot.reply_to(message, "⚠️ Invalid input.")

async def main():
    await bot.infinity_polling()

# Main function call
if __name__ == '__main__':
    asyncio.run(main())