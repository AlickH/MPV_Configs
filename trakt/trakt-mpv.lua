-- GLOBAL VARS:
Current_action = ""

--config = os.getenv("HOME") .. "/.config/mpv/scripts/trakt-mpv/config.json"
--
--function file_exists(file)
--local f = io.open(file, "rb")
--if f then f:close() end
--return f ~= nil
--end
--
---- get all lines from a file, returns an empty 
---- list/table if the file does not exist
--function lines_from(file)
--if not file_exists(file) then return {} end
--lines = {}
--for line in io.lines(file) do 
--lines[#lines + 1] = line
--end
--return lines
--end
--
--function mysplit (inputstr, sep)
--if sep == nil then
--sep = "%s"
--end
--local t={}
--for str in string.gmatch(inputstr, "([^"..sep.."]+)") do
--table.insert(t, str)
--end
--return string.match(t[2], [["([^"]+)]])
--end
--
--local lines = lines_from(config)
--
--local access_token = mysplit(lines[3], ":")
--local client_id = mysplit(lines[6], ":")
--
-- HELPER FUNCTIONS:
-- Joins two tables
local function merge_tables(t1, t2)
for k,v in ipairs(t2) do
table.insert(t1, v)
end 

return t1
end

local function sleep(n)
    os.execute("sleep " .. tonumber(n))
end

-- Calls the Python file
local function evoque_python(flags)
    -- Find the path
    local location

    if os.getenv("HOME") == nil then
        -- If you are using Windows, it will assume you are using mpv.net
        location = os.getenv("APPDATA") .. "/mpv.net/Scripts/trakt-mpv/main.py"
    else
        -- If you are using Linux, it will assume you are using mpv
        location = os.getenv("HOME") .. "/.config/mpv/scripts/trakt-mpv/main.py"
    end

    -- Add the flags
    local args = merge_tables({ "python", location }, flags)

    -- Call the file
    local r = mp.command_native({
        name = "subprocess",
        capture_stdout = true,
        args = args,
    })

    return r.status, r.stdout
end

-- Sends a message
local function send_message(msg, color, time)
    local ass_start = mp.get_property_osd("osd-ass-cc/0")
    local ass_stop = mp.get_property_osd("osd-ass-cc/1")
    mp.osd_message(ass_start .. "{\\1c&H" .. color .. "&}" .. msg .. ass_stop, time)
end

-- Activate Function
local function activated()
    local status, output = evoque_python({"--auth"})

    if status == 0 then
        send_message("It's done. Enjoy!", "00FF00", 3)
        mp.remove_key_binding("auth-trakt")
    else
        send_message("Damn, there was an error in Python :/ Check the console for more info.", "0000FF", 4)
    end
end

local function activation()
    send_message("Querying trakt.tv... Hold tight", "FFFFFF", 10)
    local status, output = evoque_python({"--code"})

    if status == 0 then
        send_message("Open https://trakt.tv/activate and type: " .. output .. "\nPress x when done", "FF8800", 50)
        mp.remove_key_binding("auth-trakt")
        mp.add_forced_key_binding("x", "auth-trakt", activated)
    else
        send_message("Damn, there was an error in Python :/ Check the console for more info.", "0000FF", 4)
    end
end

local function _scrobble()
    local status, scrobble = evoque_python({"--scrobble", mp.get_property('media-title'), mp.get_property('percent-pos'), mp.get_property('pause')})
    if status == 24 then
        --send_message("Scrobbling:" .. scrobble, "00FF00", 2)
        sleep(5)
        _scrobble()
    elseif status == 26 then
        send_message("Scrobbled:" .. scrobble, "00FF00", 2)
        print("end")
    end
end

--local function stop_scrobble()
--  os.execute('curl "https://api.trakt.tv/checkin" --request DELETE -H "Content-Type: application/json" -H "Authorization: Bearer ' .. access_token ..'" -H "trakt-api-version: 2" -H "trakt-api-key: ' .. client_id .. '"')
--end

-- Checkin Function
local function checkin()
    local status, scrobble = evoque_python({"--query", mp.get_property('media-title'), mp.get_property('percent-pos'), mp.get_property('pause')})

    if status == 0 then
        send_message("Scrobbling... " .. scrobble, "00FF00", 2)
        _scrobble()
    elseif status == 14 then
        send_message("Couldn't find the show in trakt", "0000FF", 2)
    else
        send_message("Unable to scrobble " .. scrobble, "0000FF", 2)
    end
end

-- MAIN FUNCTION

local function on_file_start(event)
    local status, output = evoque_python({"--hello"})
    -- local info = 0

    -- Check status and act accordingly
    if status == 10 then
        -- Plugin is yet to be configured
        send_message("[trakt-mpv] Please add your client_id and client_secret to config.json!" ..output , "0000FF", 4)
        return
    elseif status == 11 then
        -- Plugin has to authenticate
        send_message("[trakt-mpv] Press X to authenticate with Trakt.tv", "FF8800", 4)
        mp.add_forced_key_binding("x", "auth-trakt", activation)
    elseif status == 0 then
        checkin()
    end
end

mp.register_event("file-loaded", on_file_start)