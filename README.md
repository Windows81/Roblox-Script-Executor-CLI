<h1 align="center">R𝒮𝐸𝒳EC</h1>

**R**oblox **S**cript **Exec**utor (rsexec) is a command-line interface that primarily uses the WeAreDevs API to run scripts on the Rōblox client. Sister repository to [Personal Roblox Client Scripts](https://github.com/Windows81/Personal-Roblox-Client-Scripts).

To run my program, make sure Python is installed and that you're using Windows.

```console
python scrc/main.py
```

## Examples of use

The commands shown do not reflect whatever is available in the Lua `getrenv()` or `getfenv()` environments.

### Basic Syntax

```
> output 6+4
10
```

```
> output "string"
string
```

```
> output workspace
game.Workspace
```

The prefix `output` can be substituted for `o`.

### Loadstrings

Like any good script execution platform, Rsexec should be able to run scripts from the internet. The name `loadstring` is misleading here because unlike its Lua counterpart, it also grabs Lua code from a provided URL.

```
> ls 'https://raw.githubusercontent.com/EdgeIY/infiniteyield/master/source'
```

This works more-or-less the same as:

```
loadstring(game:HttpGet('https://raw.githubusercontent.com/EdgeIY/infiniteyield/master/source'))()
```

The prefix `ls` can be substituted for `loadstring`.

### Single-Line Snippets

```
> snippet game.Players.LocalPlayer.Character.Humanoid.Health = 0
```

Your character should die.
The prefix `snippet` can be substituted for `snip` or `s`.

### Multi-Line Snippets

Multi-line snippets keep accepting input up to the first empty line. Useful for prototyping ... I guess?

```
> multiline
game.Players.LocalPlayer.Character.Humanoid.Health = 0

> o 6
6
```

That's another way your character can die. It also prints 6 for your convenience.
The prefix `multiline` can be substituted for `ml` or `m`.

### Executing Scripts in `/workspace`

```
> chat "I'm exploiting and probably will catch someone's attention!"
```

If `/workspace/chat.lua` exists, it will be executed, with global table `_E.ARGS` initialised as:

```lua
{"I'm exploiting and probably will catch someone's attention!"}
```

Some scripts return stuff by initialising the `_E.RETURN` global table.

```
> plr 'ar'
game.Players.MechaArtoGamer
```

### Nesting Calls

```
> del [[tree game.Workspace:GetDescendants()]]
```

From `/workspace/tree.lua`, returns a list of all objects in your Workspace.

Then, from `/workspace/del.lua`, deletes everything in the list.

### Output Formatting

To produce human-likeable output, some workspace scripts print a custom string when called at the top level. These callee scripts initialise an optional `_E.OUTPUT` table near the end of the body.

Many of those custom outputs use ANSI colour codes to improve readability.

I recommend that `_E.OUTPUT` should contain only a single string.

```
> tree game.ReplicatedStorage
[02] game.ReplicatedStorage.EmoteBar {ModuleScript}
[03] game.ReplicatedStorage.EmoteBar.clientConfig {ModuleScript}
[03] game.ReplicatedStorage.EmoteBar.emotes {ModuleScript}
[03] game.ReplicatedStorage.EmoteBar.enums {ModuleScript}
[03] game.ReplicatedStorage.EmoteBar.events {ModuleScript}
[03] game.ReplicatedStorage.EmoteBar.getEmote {ModuleScript}
[03] game.ReplicatedStorage.EmoteBar.lockEmote {ModuleScript}
[03] game.ReplicatedStorage.EmoteBar.playEmote {ModuleScript}
[03] game.ReplicatedStorage.EmoteBar.serverConfig {ModuleScript}
[03] game.ReplicatedStorage.EmoteBar.setEmotes {ModuleScript}
[03] game.ReplicatedStorage.EmoteBar.setGuiVisibility {ModuleScript}
[03] game.ReplicatedStorage.EmoteBar.types {ModuleScript}
[03] game.ReplicatedStorage.EmoteBar.unlockEmote {ModuleScript}
...
```

However, this behaviour is not applied when done from a nested call. The following snippet will print a usable Lua table:

```
> o [[tree game.ReplicatedStorage]]
{
  game.ReplicatedStorage.EmoteBar,
  game.ReplicatedStorage.EmoteBar.clientConfig,
  game.ReplicatedStorage.EmoteBar.emotes,
  game.ReplicatedStorage.EmoteBar.enums,
  game.ReplicatedStorage.EmoteBar.events,
  game.ReplicatedStorage.EmoteBar.getEmote,
  game.ReplicatedStorage.EmoteBar.lockEmote,
  game.ReplicatedStorage.EmoteBar.playEmote,
  game.ReplicatedStorage.EmoteBar.serverConfig,
  game.ReplicatedStorage.EmoteBar.setEmotes,
  game.ReplicatedStorage.EmoteBar.setGuiVisibility,
  game.ReplicatedStorage.EmoteBar.types,
  game.ReplicatedStorage.EmoteBar.unlockEmote,
...
```

### Functions

```
> tree game.workspace [[function return a1.Parent.Name == 'Head']]
[06] game.Workspace.InteractiveModels.AvatarEditorModel.NpcModel.Head.Head {WrapTarget}
[06] game.Workspace.InteractiveModels.AvatarEditorModel.NpcModel.Head.NeckRigAttachment {Attachment}
[06] game.Workspace.InteractiveModels.AvatarEditorModel.NpcModel.Head.FaceFrontAttachment {Attachment}
[06] game.Workspace.InteractiveModels.AvatarEditorModel.NpcModel.Head.HatAttachment {Attachment}
[06] game.Workspace.InteractiveModels.AvatarEditorModel.NpcModel.Head.HairAttachment {Attachment}
[06] game.Workspace.InteractiveModels.AvatarEditorModel.NpcModel.Head.FaceCenterAttachment {Attachment}
[06] game.Workspace.InteractiveModels.AvatarEditorModel.NpcModel.Head.Neck {Motor6D}
...
```

The result of `/workspace/tree.lua` here is every object in the Workspace whose parent's name is 'Head'.

The string:

```
[[function return a1.Parent.Name == 'Head']]
```

...is substituted with:

```
(function(a1, a2, ...) return a1.Parent.Name == 'Head' end)
```

The prefix `function` can be substituted for `func` or `f`.

### Lambdas

```
> tree game.workspace [[lambda a1.Parent.Name == 'Head']]
[06] game.Workspace.InteractiveModels.AvatarEditorModel.NpcModel.Head.Head {WrapTarget}
...
```

Lambdas work similarly to the `f` prefix, but adds the `return` keyword prior to the function body.

The string:

```
[[lambda a1.Parent.Name == 'Head']]
```

...is replaced with:

```
(function(a1, a2, ...) return a1.Parent.Name == 'Head' end)
```

The prefix `lambda` can be substituted for `l`.
