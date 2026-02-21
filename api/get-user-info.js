export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ success:false, msg:'Method not allowed' });
  }

  const { username } = req.body;

  return res.status(200).json({
    success: true,
    data: {
      username,
      uid: "123456789",
      first_name: "Test",
      last_name: "User",
      profile_picture_url: ""
    }
  });
}
