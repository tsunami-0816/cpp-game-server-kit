UPDATE users SET password_hash='55baa6968eec5d9d7117c507fb2aa381cfd9c85e018733020b7ad58a21f7388c' WHERE username='user1';
UPDATE users SET password_hash='63e48047827db95821f831780355ecaf617d1ca69474c4a39f8902d24fa3a5e6' WHERE username='user2';
SELECT username, password_hash FROM users;
