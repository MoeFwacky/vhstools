# VHS Tools - Streamlining Video Analysis with Automation and AI

## Introduction

VHS Tools is a powerful and user-friendly application designed to simplify the process of extracting, analyzing, and identifying clips from large video files of old broadcast TV content, often taken from digitized VHS tapes. Whether you're an experienced video archivist or new to the world of preservation, VHS Tools offers a comprehensive solution for navigating through extensive footage and transforming it into organized, shareable content.

## Features

- **Scanner and Splitter:** The Scanner analyzes video frames for brightness and audio tracks for loudness levels, storing data in a JSON file. The Splitter then utilizes this data, along with values from the `config.ini` file, to extract individual clips and save them in a subdirectory named after the parent video file. This feature is optimized to identify commercials, promos, and other non-show content typically at lengths of 10, 15, 20, 30, and 60 seconds.

- **Clip Evaluation and Management:** Evaluate generated clips by selecting "View Unidentified Clips" from the Edit menu. Access a new window populated with associated data and a looped clip preview. Evaluate clips for completeness and identification, categorizing them as needed using the Recut Needed and Do Not Identify buttons.

- **Clip Recutting:** In the _recut subdirectory, edit segments of clips that require adjustments, such as overly segmented or combined clips. Use the Start Frame and End Frame buttons to autofill the frame fields, ensuring precision. Extract clips with updated segments for smoother integration into the identification process.

- **Audio Normalization:** Normalize audio levels across clips before identification to ensure consistent quality. The Audio Normalizer function adjusts peak audio to 0 dB, enhancing the overall viewing experience and ensuring uniform audio levels.

- **AI-Powered Identification:** Utilize the Identifier feature to process unidentified files. Extract audio transcripts using Whisper, perform OCR, logo detection, and label detection on select frames of each clip. The resulting data is sent to ChatGPT for further analysis, which generates JSON-format information including title, summary, category tags, and filenames. This data is then applied to metadata and filenames for each clip.

- **Upload to Internet Archive and YouTube:** After identification, upload clips to desired platforms. Choose between full video or clip uploads for the Internet Archive or YouTube. Follow prompts to authorize script access to your YouTube channel if necessary. Select files for upload and use associated Clip Data Files to enhance metadata. Note that the YouTube API allows up to six uploads per day by default.

## Installation and Setup

1. **Download the Package from GitHub:** Obtain the VHS Tools package from this repository.

2. **Install VLC Player (64-bit):** Install the 64-bit version of VLC Player, a requirement for VHS Tools.

3. **Install Tesseract:** Install Tesseract, which supports optical character recognition tasks.

4. **Obtain an OpenAI API Key:** Obtain an OpenAI API key to enable tasks like transcribing audio and video identification.

5. **Secure Internet Archive Keys:** Access and generate the necessary keys from the Internet Archive to enable seamless upload and archiving of your digitized tapes and clips.

6. **Acquire Google OAuth2 JSON with YouTube API Permissions:** Set up Google OAuth2 credentials with YouTube API permissions to authorize VHS Tools for uploading videos to your channel.

7. **Authenticate User Account for the Google Vision API:** Authenticate Google Vision tools for text recognition, logo detection, and object detection using your Google Cloud account.

8. **Configure Config File Fields:** Define the fields in the configuration file (config.ini) to manage various settings, ensuring no essential sections are left empty.

## Contributing

Contributions to improve and enhance VHS Tools are welcome. If you encounter issues or have suggestions, please report them on the [GitHub repository's issue tracker](https://github.com/yourusername/vhs-tools/issues).

## License

This project is licensed under the [GNU General Public License](LICENSE).

---

Developed by [Moe Fwacky](https://github.com/MoeFwacky)
