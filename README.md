# myspringbootnew

---
상황 : 주형, 태수 작업 중 주형과 태수의 branch에 각각 커밋을 함

main branch에서 주형의 branch것을 merge
```text
LX@PC10 MINGW64 ~/Desktop/myspringbootnew (main)
$ git merge origin/feat/del-joohyung
Updating cb429ae..7ae99c0
Fast-forward
 src/main/java/lx/edu/springboot/controller/HelloController.java | 4 ++++
 1 file changed, 4 insertions(+)
```
성공적
---

---
주형 branch merge이후 태수 branch를 merge
```text
LX@PC10 MINGW64 ~/Desktop/myspringbootnew (main)
$ git merge origin/feat/del-taesu1
Auto-merging src/main/java/lx/edu/springboot/controller/HelloController.java
CONFLICT (content): Merge conflict in src/main/java/lx/edu/springboot/controller
/HelloController.java
Automatic merge failed; fix conflicts and then commit the result.
```
CONFLICT 발생
---

---
git status를 쳐서 both modified를 확인
```text
LX@PC10 MINGW64 ~/Desktop/myspringbootnew (main|MERGING)
$ git status
On branch main
Your branch is ahead of 'origin/main' by 1 commit.
  (use "git push" to publish your local commits)

You have unmerged paths.
  (fix conflicts and run "git commit")
  (use "git merge --abort" to abort the merge)

Changes to be committed:
        modified:   src/main/java/lx/edu/springboot/controller/AddrBookController.java
        modified:   src/main/java/lx/edu/springboot/dao/AddrBookDAO.java
        modified:   src/main/java/lx/edu/springboot/vo/AddrBookVO.java
        modified:   src/main/resources/mapper/mapper-addrbook.xml
        new file:   src/main/resources/templates/addrbook_edit_form.html
        modified:   src/main/resources/templates/addrbook_list.html

Unmerged paths:
  (use "git add <file>..." to mark resolution)
        both modified:   src/main/java/lx/edu/springboot/controller/HelloController.java
```
---

<img width="1194" height="635" alt="image" src="https://github.com/user-attachments/assets/69f42d13-d6e9-4a62-840c-f163f190c64e" />

both modified:   src/main/java/lx/edu/springboot/controller/HelloController.java

여기로 들어가서 vscode, 메모장 등 열어서 <<<<< ====== >>>> 있는 부분들 제거해주고 어디서 했던지 저장만 해놓으면 됨

---
```text
LX@PC10 MINGW64 ~/Desktop/myspringbootnew (main|MERGING)
$ git add .

LX@PC10 MINGW64 ~/Desktop/myspringbootnew (main|MERGING)
$ git commit -m "충돌제거"
[main 402cdd9] 충돌제거

LX@PC10 MINGW64 ~/Desktop/myspringbootnew (main)
$ git push origin main
Enumerating objects: 28, done.
Counting objects: 100% (28/28), done.
Delta compression using up to 16 threads
Compressing objects: 100% (7/7), done.
Writing objects: 100% (10/10), 750 bytes | 750.00 KiB/s, done.
Total 10 (delta 4), reused 0 (delta 0), pack-reused 0 (from 0)
remote: Resolving deltas: 100% (4/4), completed with 4 local objects.
To https://github.com/taesu666/myspringbootnew.git
   cb429ae..402cdd9  main -> main
```
이러면 충돌 오류 해결
---
